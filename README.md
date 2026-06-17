# Melio Marketing Intelligence Agent

AI-powered daily funnel reporting and email anomaly detection, built with Claude + Cowork.

**Live output:** Slack channel `#performance-marketing-monitoring`  
**First report delivered:** Jun 17, 2026 at 12:20 PM  
**Scheduled cadence:** Daily at 9:00 AM (22 reports/month, ~110 anomaly checks/month)

---

## What it does

### 1. Daily Funnel Report
- Queries Snowflake live for activations, FTC/FTS, MQL (by grade A/B/C/D), CVR, and marketing spend
- Breaks down all metrics by source: Organic, Search Brand, Search Non Brand, Social, Affiliates & Inf
- Auto-detects anomalies: any metric dropping >10% vs prior month triggers an alert
- Generates an English MTD summary with key insights
- Delivers a fully formatted Slack report in ~4 seconds

**Performance (measured):**
- Snowflake query: 1.3s execution, 2.7s total, ~2GB scanned
- Slack delivery: ~1s
- Total end-to-end: ~4 seconds

### 2. Email Marketing Monitor
- Tracks campaign delivery rates, open rates, and bounce rates
- Fires automatic Slack alerts when metrics deviate from expected ranges
- Used by the retention team (4 members) as a net-new monitoring capability

---

## Impact

- 🆕 Two net-new capabilities — neither existed before this project
- 🚨 7 anomalies auto-detected on day 1 (Social MQL −65%, Search Brand FTC −17.2%, MQL Grade C −26.6%)
- 📅 Scheduled daily — projected 22 reports/month, ~110 anomaly checks/month
- 👥 Retention team (4 members) receives real-time email alerts for the first time
- 📉 Steps to get a daily funnel snapshot: 12+ (manual Tableau) → 1 (automated, ~4 sec)

---

## Setup & Deployment

### 1. Requirements
```bash
pip install snowflake-connector-python slack-sdk python-dotenv
```

### 2. Environment variables
Create a `.env` file (never commit this):
```
SLACK_BOT_TOKEN=xoxb-...
SNOWFLAKE_USER=your_user
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_WAREHOUSE=ANALYST_WH
```

### 3. Snowflake connection
The script uses `externalbrowser` authentication by default (SSO). For production/automated runs, switch to key-pair auth:
```python
snowflake.connector.connect(
    user=os.environ["SNOWFLAKE_USER"],
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "ANALYST_WH"),
    database="PROD",
    schema="ANALYTICS",
    private_key=load_private_key(),   # key-pair for headless auth
)
```

### 4. Run manually
```bash
python daily_report.py
```

### 5. Schedule with cron (daily at 9:00 AM)
```bash
crontab -e
```
Add:
```
0 9 * * 1-5 cd /path/to/melio-marketing-agent && python daily_report.py
```

### 6. Schedule with Claude Cowork (recommended)
In Cowork, use the `schedule` skill:
> "Run daily_report.py every weekday at 9 AM"

This registers a managed scheduled task with logging and error handling.

---

## Anomaly detection logic

A metric is flagged when:
```python
delta = (current_month_bd_value - prior_month_bd_value) / prior_month_bd_value
if delta <= -0.10:
    alert(metric, delta, label="NEW" or "ONGOING")
```

Thresholds:
- `>10% drop` → alert
- Comparison is BD-normalized (same business day number, not calendar date)

---

## Snowflake query logic

See `sql/funnel_query.sql` for the full query.

Key design decisions:
- **BD normalization:** uses `business_agg_inc_non_business_days` to compare same BD across months (fair MoM)
- **Filters:** SMB only, excludes Viral/QB/Partners/Intuit flows
- **Source type mapping:** applied at query time (adwords+brand keyword → Search Brand, etc.)
- **Deduplication:** COUNT on organization_id-level metrics; confirmed no fan-out from multi-row orgs

---

## Repository structure

```
melio-marketing-agent/
├── daily_report.py        # Main script: Snowflake → anomaly detection → Slack
├── requirements.txt       # Python dependencies
├── sql/
│   └── funnel_query.sql   # Full Snowflake query with BD normalization
└── README.md
```
