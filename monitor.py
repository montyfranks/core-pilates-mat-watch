#!/usr/bin/env python3
"""
Core Pilates observation-slot watcher.

Checks the studio's observation feed and sends a push notification (via ntfy)
when a matching class has places: either a brand-new class, or a full class
where a place has just opened up (a cancellation).

Settings come from environment variables (set in the GitHub workflow):
  NTFY_TOPIC   - required. The ntfy topic her phone is subscribed to.
  STUDIO       - studio name to match (default "Chelsea")
  CLASS_MATCH  - word that must appear in the class title (default "Matwork")
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

FEED_URL = "https://corepilatesstudios.co.uk/wp-json/core-observations/v1/classes"
BOOK_URL = "https://corepilatesstudios.co.uk/class-observation/"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
UA = "Mozilla/5.0 (observation-slot-watcher)"

STUDIO = os.environ.get("STUDIO", "Chelsea").lower()
CLASS_MATCH = os.environ.get("CLASS_MATCH", "Matwork").lower()
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
LONDON = ZoneInfo("Europe/London")


HEALTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "health.json")
ALERT_AFTER = 12  # consecutive failed checks (~1 hour) before the run is marked failed


def fetch_classes():
    """Fetch the feed, retrying a few times so a brief website blip doesn't count as a failure."""
    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(FEED_URL, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            if not isinstance(data, list):
                raise ValueError("feed did not return a list of classes")
            return data
        except Exception as e:
            last_err = e
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(5 * (attempt + 1))
    raise last_err


def load_failures():
    try:
        with open(HEALTH_FILE) as f:
            return int(json.load(f).get("consecutive_failures", 0))
    except Exception:
        return 0


def save_failures(n):
    if n == load_failures():
        return
    if n == 0:
        try:
            os.remove(HEALTH_FILE)
        except FileNotFoundError:
            pass
        return
    with open(HEALTH_FILE, "w") as f:
        json.dump({"consecutive_failures": n}, f)
        f.write("\n")


def matches(c):
    return STUDIO in str(c.get("studio", "")).lower() and CLASS_MATCH in str(c.get("title", "")).lower()


def is_future(c):
    # starts_at is UTC; date/time fields are UK local
    try:
        start = datetime.strptime(c["date"] + " " + c["time"], "%d/%m/%Y %H:%M").replace(tzinfo=LONDON)
        return start > datetime.now(LONDON)
    except Exception:
        return True


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)
        f.write("\n")


def notify(title, message, priority="high", tags="tada"):
    if not TOPIC:
        print("NTFY_TOPIC not set; would have sent:", title, "|", message)
        return
    body = json.dumps({
        "topic": TOPIC,
        "title": title,
        "message": message,
        "click": BOOK_URL,
        "priority": {"high": 4, "default": 3, "low": 2}.get(priority, 4),
        "tags": [tags],
        "actions": [{"action": "view", "label": "Book now", "url": BOOK_URL}],
    }).encode()
    req = urllib.request.Request("https://ntfy.sh", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    urllib.request.urlopen(req, timeout=30).read()


def describe(c):
    d = datetime.strptime(c["date"], "%d/%m/%Y").strftime("%a %d %b")
    places = c.get("available", 0)
    return f"{d} {c['time']} - {c['title']} with {c['instructor']} ({places} place{'s' if places != 1 else ''})"


def main():
    classes = [c for c in fetch_classes() if matches(c) and is_future(c)]
    current = {str(c["id"]): int(c.get("available") or 0) for c in classes}
    previous = load_state()

    if previous is None:
        # First run: remember what's there now and send a test ping.
        save_state(current)
        open_now = [c for c in classes if int(c.get("available") or 0) > 0]
        msg = (f"Watching {len(classes)} {CLASS_MATCH.title()} observation(s) at {STUDIO.title()}. "
               f"{len(open_now)} currently have places. You'll get a ping when a new one appears or a place opens up.")
        if open_now:
            msg += "\n\nOpen now:\n" + "\n".join(describe(c) for c in open_now)
        notify("Pilates observation alerts are live", msg, priority="default", tags="white_check_mark")
        print(msg)
        return

    new_open, freed = [], []
    for c in classes:
        cid, avail = str(c["id"]), int(c.get("available") or 0)
        if avail <= 0:
            continue
        if cid not in previous:
            new_open.append(c)
        elif previous[cid] <= 0:
            freed.append(c)

    if new_open:
        title = "New Chelsea mat observation" + ("s" if len(new_open) > 1 else "") + " - book now"
        notify(title, "\n".join(describe(c) for c in new_open))
    if freed:
        title = "Place opened up on a mat observation"
        notify(title, "\n".join(describe(c) for c in freed))

    print(f"{len(classes)} matching classes; {len(new_open)} new, {len(freed)} freed up.")
    if current != previous:
        save_state(current)


if __name__ == "__main__":
    try:
        main()
        save_failures(0)
    except Exception as e:
        n = load_failures() + 1
        save_failures(n)
        print(f"Check failed ({n} in a row): {e}", file=sys.stderr)
        # Stay quiet for short outages; only mark the run failed (which emails you)
        # once it has been failing for about an hour, then every ~6 hours after.
        if n == ALERT_AFTER or (n > ALERT_AFTER and (n - ALERT_AFTER) % 72 == 0):
            sys.exit(1)
