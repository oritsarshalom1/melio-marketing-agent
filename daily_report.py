"""
Daily Activation & Funnel Report – Slack Bot
SMB only | excl. Viral, QB, Partners
Table layout: Total row (bold) + source breakdown in one unified table per section.
"""

import os
import snowflake.connector
from slack_sdk import WebClient
from datetime import date, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
SLACK_TOKEN     = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL   = "C0BASU9G885"
ALERT_THRESHOLD = 10

# ── Snowflake ─────────────────────────────────────────────────────────────────
def get_snowflake_conn():
    return snowflake.connector.connect(
        user          = os.environ["SNOWFLAKE_USER"],
        account       = os.environ["SNOWFLAKE_ACCOUNT"],
        warehouse     = os.environ.get("SNOWFLAKE_WAREHOUSE", "ANALYST_WH"),
        database      = "PROD",
        schema        = "ANALYTICS",
        authenticator = "externalbrowser",
    )

# ── SQL ───────────────────────────────────────────────────────────────────────
SQL = """
WITH today_bd AS (
    SELECT NUMBER_OF_BUS_DAY AS bd
    FROM prod.analytics.business_agg_inc_non_business_days
    WHERE _DATE = DATEADD('day', -1, CURRENT_DATE())
),
base AS (
    SELECT
        m.organization_id,
        o.melio_ap_completed_first_payment_date                                        AS melio_ap_activation,
        o.melio_ar_completed_first_payment_date                                        AS melio_ar_activation,
        LEAST(
            COALESCE(o.melio_ap_completed_first_payment_date, o.melio_ar_completed_first_payment_date),
            COALESCE(o.melio_ar_completed_first_payment_date, o.melio_ap_completed_first_payment_date)
        )                                                                              AS melio_activation,
        o.melio_ap_created_first_payment_date                                          AS melio_fts,
        o.ap_first_payment_attempt_created_datetime                                    AS melio_ftc,
        m.registration_datetime,
        o.is_real_business,
        LEFT(o.org_fit_grade, 1) AS fit_grade,
        CASE
            WHEN m.source IN ('adwords','microsoft-ads') THEN
                CASE WHEN LOWER(m.campaign) LIKE '%brand%' THEN 'Search Brand'
                     ELSE 'Search Non Brand' END
            WHEN m.source IN ('facebook','gdn','youtube','reddit','tiktok','li','linkedin','fb')
                THEN 'Social'
            WHEN m.source_group = 'online untracked' THEN 'Organic'
            WHEN m.source_group IN ('publications and influencers','referrer program')
                OR m.source IN ('financesonline','capterra') THEN 'Affiliates & Inf'
            ELSE 'Other'
        END AS source_type
    FROM prod.analytics.marketing_organization_dim m
    INNER JOIN prod.analytics.organization_dim o ON m.organization_id = o.organization_id
    WHERE
        m.company_type = 'smb'
        AND o.partner_name = 'melio'
        AND m.is_guest = FALSE
        AND m.flow NOT IN ('Viral', 'Partnerships', 'Intuit')
        AND m.organization_create_origin NOT IN (
            'qbdt-mac','qbdt-windows','qbm-android','qbm-ios','qbr-android','qbr-ios'
        )
        AND (
            o.melio_ap_completed_first_payment_date
                >= DATE_TRUNC('month', DATEADD('month', -2, CURRENT_DATE()))
            OR o.melio_ar_completed_first_payment_date
                >= DATE_TRUNC('month', DATEADD('month', -2, CURRENT_DATE()))
            OR o.melio_ap_created_first_payment_date
                >= DATE_TRUNC('month', DATEADD('month', -2, CURRENT_DATE()))
            OR o.ap_first_payment_attempt_created_datetime
                >= DATE_TRUNC('month', DATEADD('month', -2, CURRENT_DATE()))
            OR m.registration_datetime
                >= DATE_TRUNC('month', DATEADD('month', -2, CURRENT_DATE()))
        )
),
with_bd AS (
    SELECT b.*,
        DATE_TRUNC('month', b.melio_activation::DATE)       AS activation_month,
        act_bd.NUMBER_OF_BUS_DAY                             AS activation_bd,
        DATE_TRUNC('month', b.melio_ap_activation::DATE)    AS ap_activation_month,
        ap_bd.NUMBER_OF_BUS_DAY                              AS ap_activation_bd,
        DATE_TRUNC('month', b.melio_ar_activation::DATE)    AS ar_activation_month,
        ar_bd.NUMBER_OF_BUS_DAY                              AS ar_activation_bd,
        DATE_TRUNC('month', b.melio_fts::DATE)              AS fts_month,
        fts_bd.NUMBER_OF_BUS_DAY                             AS fts_bd,
        DATE_TRUNC('month', b.melio_ftc::DATE)              AS ftc_month,
        ftc_bd.NUMBER_OF_BUS_DAY                             AS ftc_bd,
        DATE_TRUNC('month', b.registration_datetime::DATE)  AS reg_month,
        reg_bd.NUMBER_OF_BUS_DAY                             AS reg_bd
    FROM base b
    LEFT JOIN prod.analytics.business_agg_inc_non_business_days act_bd ON act_bd._DATE = b.melio_activation::DATE
    LEFT JOIN prod.analytics.business_agg_inc_non_business_days ap_bd  ON ap_bd._DATE  = b.melio_ap_activation::DATE
    LEFT JOIN prod.analytics.business_agg_inc_non_business_days ar_bd  ON ar_bd._DATE  = b.melio_ar_activation::DATE
    LEFT JOIN prod.analytics.business_agg_inc_non_business_days fts_bd ON fts_bd._DATE = b.melio_fts::DATE
    LEFT JOIN prod.analytics.business_agg_inc_non_business_days ftc_bd ON ftc_bd._DATE = b.melio_ftc::DATE
    LEFT JOIN prod.analytics.business_agg_inc_non_business_days reg_bd ON reg_bd._DATE = b.registration_datetime::DATE
)
SELECT
    source_type,
    (SELECT bd FROM today_bd) AS report_bd,
    COUNT(CASE WHEN activation_month    = DATE_TRUNC('month', CURRENT_DATE())                     AND activation_bd    <= (SELECT bd FROM today_bd) THEN 1 END) AS act_total_cur,
    COUNT(CASE WHEN activation_month    = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND activation_bd    <= (SELECT bd FROM today_bd) THEN 1 END) AS act_total_prev,
    COUNT(CASE WHEN ap_activation_month = DATE_TRUNC('month', CURRENT_DATE())                     AND ap_activation_bd <= (SELECT bd FROM today_bd) THEN 1 END) AS act_ap_cur,
    COUNT(CASE WHEN ap_activation_month = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND ap_activation_bd <= (SELECT bd FROM today_bd) THEN 1 END) AS act_ap_prev,
    COUNT(CASE WHEN ar_activation_month = DATE_TRUNC('month', CURRENT_DATE())                     AND ar_activation_bd <= (SELECT bd FROM today_bd) THEN 1 END) AS act_ar_cur,
    COUNT(CASE WHEN ar_activation_month = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND ar_activation_bd <= (SELECT bd FROM today_bd) THEN 1 END) AS act_ar_prev,
    COUNT(CASE WHEN fts_month           = DATE_TRUNC('month', CURRENT_DATE())                     AND fts_bd           <= (SELECT bd FROM today_bd) THEN 1 END) AS fts_cur,
    COUNT(CASE WHEN fts_month           = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND fts_bd           <= (SELECT bd FROM today_bd) THEN 1 END) AS fts_prev,
    COUNT(CASE WHEN ftc_month           = DATE_TRUNC('month', CURRENT_DATE())                     AND ftc_bd           <= (SELECT bd FROM today_bd) THEN 1 END) AS ftc_cur,
    COUNT(CASE WHEN ftc_month           = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND ftc_bd           <= (SELECT bd FROM today_bd) THEN 1 END) AS ftc_prev,
    COUNT(CASE WHEN reg_month = DATE_TRUNC('month', CURRENT_DATE())                     AND reg_bd <= (SELECT bd FROM today_bd) AND is_real_business=TRUE THEN 1 END) AS real_biz_cur,
    COUNT(CASE WHEN reg_month = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND reg_bd <= (SELECT bd FROM today_bd) AND is_real_business=TRUE THEN 1 END) AS real_biz_prev,
    COUNT(CASE WHEN reg_month = DATE_TRUNC('month', CURRENT_DATE())                     AND reg_bd <= (SELECT bd FROM today_bd) AND is_real_business=TRUE AND fit_grade='A' THEN 1 END) AS real_biz_a_cur,
    COUNT(CASE WHEN reg_month = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND reg_bd <= (SELECT bd FROM today_bd) AND is_real_business=TRUE AND fit_grade='A' THEN 1 END) AS real_biz_a_prev,
    COUNT(CASE WHEN reg_month = DATE_TRUNC('month', CURRENT_DATE())                     AND reg_bd <= (SELECT bd FROM today_bd) AND is_real_business=TRUE AND fit_grade='B' THEN 1 END) AS real_biz_b_cur,
    COUNT(CASE WHEN reg_month = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND reg_bd <= (SELECT bd FROM today_bd) AND is_real_business=TRUE AND fit_grade='B' THEN 1 END) AS real_biz_b_prev,
    COUNT(CASE WHEN reg_month = DATE_TRUNC('month', CURRENT_DATE())                     AND reg_bd <= (SELECT bd FROM today_bd) AND is_real_business=TRUE AND fit_grade='C' THEN 1 END) AS real_biz_c_cur,
    COUNT(CASE WHEN reg_month = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND reg_bd <= (SELECT bd FROM today_bd) AND is_real_business=TRUE AND fit_grade='C' THEN 1 END) AS real_biz_c_prev,
    COUNT(CASE WHEN reg_month = DATE_TRUNC('month', CURRENT_DATE())                     AND reg_bd <= (SELECT bd FROM today_bd) AND is_real_business=TRUE AND fit_grade='D' THEN 1 END) AS real_biz_d_cur,
    COUNT(CASE WHEN reg_month = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND reg_bd <= (SELECT bd FROM today_bd) AND is_real_business=TRUE AND fit_grade='D' THEN 1 END) AS real_biz_d_prev,
    COUNT(CASE WHEN DATE_TRUNC('week', registration_datetime::DATE) = DATE_TRUNC('week', DATEADD('day', -7,CURRENT_DATE()))  THEN 1 END) AS cvr_reg_w1,
    COUNT(CASE WHEN DATE_TRUNC('week', registration_datetime::DATE) = DATE_TRUNC('week', DATEADD('day', -7,CURRENT_DATE()))  AND melio_fts IS NOT NULL AND DATEDIFF('day', registration_datetime::DATE, melio_fts::DATE) BETWEEN 0 AND 7 THEN 1 END) AS cvr_fts_w1,
    COUNT(CASE WHEN DATE_TRUNC('week', registration_datetime::DATE) = DATE_TRUNC('week', DATEADD('day',-14,CURRENT_DATE())) THEN 1 END) AS cvr_reg_w2,
    COUNT(CASE WHEN DATE_TRUNC('week', registration_datetime::DATE) = DATE_TRUNC('week', DATEADD('day',-14,CURRENT_DATE())) AND melio_fts IS NOT NULL AND DATEDIFF('day', registration_datetime::DATE, melio_fts::DATE) BETWEEN 0 AND 7 THEN 1 END) AS cvr_fts_w2
FROM with_bd
GROUP BY source_type
ORDER BY act_total_cur DESC
"""

# ── Constants ─────────────────────────────────────────────────────────────────
CHANNEL_ORDER = ["Organic", "Search Brand", "Search Non Brand", "Affiliates & Inf", "Social", "Other"]

# ── Math helpers ──────────────────────────────────────────────────────────────
def pct(cur, prev):
    if not prev: return None
    return round((cur - prev) * 100.0 / prev, 1)

def cvr_rate(fts, reg):
    if not reg: return None
    return round(fts * 100.0 / reg, 1)

def totals_for(rows, cur_key, prev_key):
    tc = tp = 0
    for ch in CHANNEL_ORDER:
        r = rows.get(ch)
        if not r: continue
        tc += r.get(cur_key, 0)
        tp += r.get(prev_key, 0)
    return tc, tp

def fmt_d(val, suffix="%"):
    if val is None: return "–"
    if val >= 0:    return f"+{val:.1f}{suffix}"
    return f"−{abs(val):.1f}{suffix}"

def n(v): return f"{v:,}"

# ── Block helpers ─────────────────────────────────────────────────────────────
def sec(text):
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}

def div():
    return {"type": "divider"}

def source_table(rows, cur_m, *col_pairs):
    """
    Mrkdwn table: bold Total row first, then source breakdown.
    col_pairs: (header, cur_key, prev_key) — value+delta in one cell.
    """
    hdrs   = " | ".join(h for h, _, _ in col_pairs)
    aligns = " | ".join("---:" for _ in col_pairs)
    hdr    = f"| Source type | {hdrs} |\n|---|{aligns}|\n"

    tc_list, tp_list = [0] * len(col_pairs), [0] * len(col_pairs)
    source_rows = ""
    for ch in CHANNEL_ORDER:
        r = rows.get(ch)
        if not r: continue
        cells = []
        for i, (_, ck, pk) in enumerate(col_pairs):
            c, p_ = r.get(ck, 0), r.get(pk, 0)
            tc_list[i] += c
            tp_list[i] += p_
            d    = pct(c, p_)
            flag = " ⚠️" if d is not None and d <= -ALERT_THRESHOLD else ""
            cells.append(f"{n(c)} {fmt_d(d)}{flag}")
        source_rows += f"| {ch} | " + " | ".join(cells) + " |\n"

    total_cells = []
    for i in range(len(col_pairs)):
        tc, tp = tc_list[i], tp_list[i]
        d    = pct(tc, tp)
        flag = " ⚠️" if d is not None and d <= -ALERT_THRESHOLD else ""
        total_cells.append(f"*{n(tc)}* {fmt_d(d)}{flag}")
    total_row = "| *Total* | " + " | ".join(total_cells) + " |\n"

    return sec(hdr + total_row + source_rows)


def mql_source_table(rows, rb_tot, rb_a, rb_b, rb_c, rb_d):
    """MQL table: bold Total row + grade deltas per source."""
    hdr = "| Source type | Total | 🟢 A | 🔵 B | 🟡 C | 🔴 D |\n|---|---:|---:|---:|---:|---:|\n"

    def cell(tc, tp, bold=False):
        d    = pct(tc, tp)
        flag = " ⚠️" if d is not None and d <= -ALERT_THRESHOLD else ""
        s    = f"{n(tc)} {fmt_d(d)}{flag}"
        return f"*{s}*" if bold else s

    total_row = (f"| *Total* | {cell(rb_tot[0], rb_tot[1], True)} | "
                 f"{cell(rb_a[0], rb_a[1], True)} | {cell(rb_b[0], rb_b[1], True)} | "
                 f"{cell(rb_c[0], rb_c[1], True)} | {cell(rb_d[0], rb_d[1], True)} |\n")

    body = ""
    for ch in CHANNEL_ORDER:
        r = rows.get(ch)
        if not r: continue
        tc, tp = r.get("real_biz_cur", 0), r.get("real_biz_prev", 0)
        row = f"| {ch} | {cell(tc, tp)}"
        for gk in ["real_biz_a", "real_biz_b", "real_biz_c", "real_biz_d"]:
            gc = r.get(f"{gk}_cur", 0); gp = r.get(f"{gk}_prev", 0)
            row += f" | {cell(gc, gp)}"
        body += row + " |\n"

    return sec(hdr + total_row + body)


def cvr_table(rows, c1_tot, c2_tot, w1_lbl, w2_lbl):
    """CVR table: bold Total row + per-channel breakdown."""
    hdr = f"| Source | {w1_lbl} | {w2_lbl} | Δ pp |\n|---|---:|---:|---:|\n"

    def row(label, c1, c2, bold=False):
        if not c1: return ""
        d    = round(c1 - c2, 1) if c2 else None
        flag = " ⚠️" if d is not None and d <= -ALERT_THRESHOLD else ""
        c2s  = f"{c2:.1f}%" if c2 else "–"
        if bold:
            return f"| *{label}* | *{c1:.1f}%* | {c2s} | *{fmt_d(d, 'pp')}{flag}* |\n"
        return f"| {label} | {c1:.1f}% | {c2s} | {fmt_d(d, 'pp')}{flag} |\n"

    total_row = row("Total", c1_tot, c2_tot, bold=True)
    body = ""
    for ch in CHANNEL_ORDER:
        if ch not in rows: continue
        r  = rows[ch]
        c1 = cvr_rate(r.get("cvr_fts_w1", 0), r.get("cvr_reg_w1", 0))
        c2 = cvr_rate(r.get("cvr_fts_w2", 0), r.get("cvr_reg_w2", 0))
        body += row(ch, c1, c2)

    return sec(hdr + total_row + body)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    conn   = get_snowflake_conn()
    cursor = conn.cursor(snowflake.connector.DictCursor)
    cursor.execute(SQL)
    raw    = cursor.fetchall()
    conn.close()

    rows = {r["SOURCE_TYPE"]: {k.lower(): v for k, v in r.items()} for r in raw}

    today       = date.today()
    _prev       = today.replace(day=1) - timedelta(days=1)
    cur_m       = today.strftime("%b")
    prev_m      = _prev.strftime("%b")
    today_label = today.strftime("%a %b %-d, %Y")
    report_bd   = list(rows.values())[0].get("report_bd", "?") if rows else "?"
    BD          = f"BD{report_bd}"

    act_tot = totals_for(rows, "act_total_cur", "act_total_prev")
    act_ap  = totals_for(rows, "act_ap_cur",    "act_ap_prev")
    act_ar  = totals_for(rows, "act_ar_cur",    "act_ar_prev")
    fts_tot = totals_for(rows, "fts_cur",       "fts_prev")
    ftc_tot = totals_for(rows, "ftc_cur",       "ftc_prev")
    rb_tot  = totals_for(rows, "real_biz_cur",  "real_biz_prev")
    rb_a    = totals_for(rows, "real_biz_a_cur","real_biz_a_prev")
    rb_b    = totals_for(rows, "real_biz_b_cur","real_biz_b_prev")
    rb_c    = totals_for(rows, "real_biz_c_cur","real_biz_c_prev")
    rb_d    = totals_for(rows, "real_biz_d_cur","real_biz_d_prev")

    w1_start = today - timedelta(days=today.weekday() + 7)
    w2_start = w1_start - timedelta(days=7)
    w1_lbl   = f"Wk {w1_start.strftime('%-d %b')}"
    w2_lbl   = f"Wk {w2_start.strftime('%-d %b')}"

    cvr_agg = {k: sum(rows[ch].get(k, 0) for ch in CHANNEL_ORDER if ch in rows)
               for k in ("cvr_reg_w1","cvr_fts_w1","cvr_reg_w2","cvr_fts_w2")}
    c1_tot = cvr_rate(cvr_agg["cvr_fts_w1"], cvr_agg["cvr_reg_w1"])
    c2_tot = cvr_rate(cvr_agg["cvr_fts_w2"], cvr_agg["cvr_reg_w2"])

    # ── Alerts ────────────────────────────────────────────────────────────────
    alerts = []
    for label, (tc, tp) in [
        ("Activations Total", act_tot), ("Activations AP", act_ap), ("Activations AR", act_ar),
        ("FTC", ftc_tot), ("FTS", fts_tot), ("MQL", rb_tot),
    ]:
        p = pct(tc, tp)
        if p and p <= -ALERT_THRESHOLD:
            alerts.append(f"*{label}* {fmt_d(p)}")

    # ── Blocks ────────────────────────────────────────────────────────────────
    blocks = [
        {"type": "header", "text": {"type": "plain_text",
            "text": f"📊 Daily Funnel Report — {today_label}", "emoji": True}},
        sec(f"SMB only  ·  excl. Viral, QB, Partners  ·  *{BD}*  ·  ✅ = normal  ·  ⚠️ = drop >{ALERT_THRESHOLD}%"),
        div(),

        # ── Activations ───────────────────────────────────────────────────────
        sec("_📌 Activations_"),
        source_table(rows, cur_m,
            (f"Total {cur_m}", "act_total_cur", "act_total_prev"),
            (f"AP {cur_m}",   "act_ap_cur",    "act_ap_prev"),
            (f"AR {cur_m}",   "act_ar_cur",    "act_ar_prev"),
        ),
        div(),

        # ── FTC & FTS ─────────────────────────────────────────────────────────
        sec("_📌 FTC & FTS_"),
        source_table(rows, cur_m,
            (f"FTC {cur_m}", "ftc_cur", "ftc_prev"),
            (f"FTS {cur_m}", "fts_cur", "fts_prev"),
        ),
        div(),

        # ── Real Business (MQL) ───────────────────────────────────────────────
        sec("_📌 Real Business (MQL)_"),
        mql_source_table(rows, rb_tot, rb_a, rb_b, rb_c, rb_d),
        div(),

        # ── CVR → FTS ─────────────────────────────────────────────────────────
        sec("_📌 CVR → FTS  (weekly · 7-day window)_"),
        cvr_table(rows, c1_tot, c2_tot, w1_lbl, w2_lbl),
        div(),
    ]

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = ("⚠️ *Alerts — drops >{}%:*  ".format(ALERT_THRESHOLD) + "  ·  ".join(alerts)
               if alerts else "✅  All metrics within normal range.")
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": summary}]})

    # ── Send ──────────────────────────────────────────────────────────────────
    client = WebClient(token=SLACK_TOKEN)
    client.chat_postMessage(
        channel = SLACK_CHANNEL,
        text    = f"📊 Daily Funnel Report — {today_label}",
        blocks  = blocks,
    )
    print(f"✅ Sent ({BD})")

if __name__ == "__main__":
    main()
