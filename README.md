# Melio Marketing Intelligence Agent

AI-powered daily funnel reporting and email anomaly detection, built with Claude + Cowork.

## What it does

### 1. Daily Funnel Report
- Queries Snowflake live for activations, FTC/FTS, MQL (by grade), CVR, and marketing spend
- Breaks down all metrics by source type: Organic, Search Brand, Search Non Brand, Social, Affiliates & Inf
- Auto-detects anomalies: any metric dropping >10% vs prior month triggers an alert
- Generates an English MTD summary with key insights
- Delivers a fully formatted Slack report in seconds

### 2. Email Marketing Monitor
- Tracks campaign delivery rates, open rates, and bounce rates
- Fires automatic Slack alerts when metrics deviate from expected ranges
- Used by the retention team (4 members) as a net-new monitoring capability

## Impact
- 🆕 Two net-new capabilities — neither existed before this project
- 🚨 Anomaly detection: from none → <5 minutes
- 📉 Steps to get a daily funnel snapshot: 12+ (manual Tableau) → 1 (automated Slack delivery)
- 👥 Retention team receives real-time email alerts for the first time

## Setup

### Requirements
```
snowflake-connector-python
slack-sdk
python-dotenv
```

Install:
```bash
pip install snowflake-connector-python slack-sdk python-dotenv
```

### Environment variables
Create a `.env` file (never commit this):
```
SLACK_BOT_TOKEN=xoxb-...
SNOWFLAKE_USER=your_user
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_WAREHOUSE=ANALYST_WH
```

### Run
```bash
python daily_report.py
```

## Architecture

```
Snowflake (prod.analytics) 
    → Python query layer (daily_report.py)
    → Anomaly detection (>10% MoM threshold)
    → MTD summary generation (Claude)
    → Slack delivery (slack-sdk)
```

## Anomaly detection logic

A metric is flagged if:
```
(current_month_value - prev_month_value) / prev_month_value < -0.10
```

Alerts are labeled NEW (first occurrence) or ONGOING (persists from prior day).

## Snowflake query logic

See `sql/funnel_query.sql` for the full query.

Key design decisions:
- Uses `business_agg_inc_non_business_days` table to normalize by business day (BD), ensuring fair MoM comparisons
- Filters: SMB only, excludes Viral/QB/Partners flows
- Source type mapping applied at query time (adwords+brand → Search Brand, etc.)
