# Chelsea mat observation alerts

Checks Core Pilates' class-observation feed every 5 minutes and pings her iPhone when a **Chelsea Matwork** observation has places:

- a **new class** appears with places, or
- a **full class gets a place back** (someone cancels).

Tapping the notification opens the booking page.

## Setup (about 10 minutes)

### 1. Her phone: install ntfy
1. Install **ntfy** from the App Store (free, no account needed).
2. Tap **+** and subscribe to the topic: `core-mat-66de5d62fb`
3. Allow notifications when asked.

Keep the topic name to yourselves. Anyone who knows it can see or send alerts on it, which is why it has random characters at the end.

### 2. GitHub: create the repo
1. Sign in at github.com and create a new repository, e.g. `pilates-watch`. Make it **private**.
2. Upload everything in this folder, including the hidden `.github` folder. Dragging the unzipped folder onto the "upload files" page works, or use `git push`.

### 3. Add the topic as a secret
Repo → **Settings → Secrets and variables → Actions → New repository secret**
- Name: `NTFY_TOPIC`
- Value: `core-mat-66de5d62fb`

### 4. Turn it on
Repo → **Actions** tab → enable workflows if prompted → **Watch observation slots** → **Run workflow**.

Within a minute her phone should get "Pilates observation alerts are live". After that it runs on its own every 5 minutes.

## Notes
- **Changing what it watches:** edit `STUDIO` and `CLASS_MATCH` in `.github/workflows/watch.yml`. For example, set `CLASS_MATCH: Reformer`, or `STUDIO: Kensington`.
- **Speed:** GitHub's 5-minute schedule sometimes runs a few minutes late at busy times. For faster alerts, a free external pinger such as cron-job.org can trigger the workflow every minute.
- **If alerts go quiet:** check the Actions tab for red runs. A red run usually means the studio changed its website or blocked the request.
- **Automatic pause:** GitHub pauses scheduled jobs on repos with no activity for 60 days. The bot's own updates to `state.json` usually keep the repo active, but if it ever pauses, click "Enable workflow" in the Actions tab.
