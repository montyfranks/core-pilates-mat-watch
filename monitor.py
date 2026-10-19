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


def fetch_classes():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


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
    except Exception as e:
        print("Check failed:", e, file=sys.stderr)
        sys.exit(1)
