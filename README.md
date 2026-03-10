# Inventory Tracker

Automated inventory monitoring tool that watches a Microsoft Access database, checks stock levels against configurable thresholds, and sends Slack alerts when items run low.
Built for tracking balloon and stent component supplies at InSitu.

## What it does

- Queries a Microsoft Access database every 30 minutes (configurable)
- Calculates on-hand quantity as `Total Received − Total Converted`
- Fires a warning alert when stock drops to ≤ 10 units, and a critical alert at ≤ 5 units (both thresholds are configurable per item)
- You only get notified when an item crosses into a new level, not on every check
- Sends grouped alerts to one or more Slack channels via incoming webhooks
- Persists cooldown state between restarts so you don't get duplicate alerts after a restart

## Requirements

- Windows (Access ODBC driver required)
- Python 3.8+
- Network access to the Access `.mdb` file
- A Slack incoming webhook URL

## Setup

1. **Install dependencies**

```bash
cd inventory_monitor_app
pip install -r requirements.txt
```

2. **Configure**

Edit `config.json` in the project root:

- Set the `databases.access.connection_string` to point to your `.mdb` file
- Replace `SLACK-HOOK-URL-FOR-CHANNEL` with your real Slack webhook URL
- Adjust `thresholds.default_warning` and `thresholds.default_critical` as needed

You can also use environment variables instead of editing `config.json`:

| Variable | Description |
|---|---|
| `ACCESS_CONNECTION_STRING` | ODBC connection string for the Access database |
| `SLACK_WEBHOOK_1` | Slack incoming webhook URL |

3. **Run**

```bash
# Run once and exit
python inventory_monitor_app/main.py --once

# Run on a schedule (default: every 30 minutes)
python inventory_monitor_app/main.py

# Check that DB and Slack connections work
python inventory_monitor_app/main.py --health
```

## Configuration reference

```json
{
  "monitoring": {
    "interval_minutes": 30
  },
  "thresholds": {
    "default_warning": 10,
    "default_critical": 5,
    "items": {
      "19T-001": { "warning": 15, "critical": 8 }
    }
  },
  "slack": {
    "notification_cooldown_minutes": 60
  }
}
```

Per-item thresholds in `thresholds.items` override the defaults for that specific part number.
