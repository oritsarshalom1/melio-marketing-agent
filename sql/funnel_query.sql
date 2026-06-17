-- Daily Funnel Report — Snowflake Query
-- SMB only | excl. Viral, QB, Partners
-- Compares current month vs prior month, normalized by business day (BD)

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
        -- Source type mapping (mirrors marketing attribution logic)
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
    -- Activations
    COUNT(CASE WHEN activation_month    = DATE_TRUNC('month', CURRENT_DATE())                     AND activation_bd    <= (SELECT bd FROM today_bd) THEN 1 END) AS act_total_cur,
    COUNT(CASE WHEN activation_month    = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND activation_bd    <= (SELECT bd FROM today_bd) THEN 1 END) AS act_total_prev,
    COUNT(CASE WHEN ap_activation_month = DATE_TRUNC('month', CURRENT_DATE())                     AND ap_activation_bd <= (SELECT bd FROM today_bd) THEN 1 END) AS act_ap_cur,
    COUNT(CASE WHEN ap_activation_month = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND ap_activation_bd <= (SELECT bd FROM today_bd) THEN 1 END) AS act_ap_prev,
    COUNT(CASE WHEN ar_activation_month = DATE_TRUNC('month', CURRENT_DATE())                     AND ar_activation_bd <= (SELECT bd FROM today_bd) THEN 1 END) AS act_ar_cur,
    COUNT(CASE WHEN ar_activation_month = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND ar_activation_bd <= (SELECT bd FROM today_bd) THEN 1 END) AS act_ar_prev,
    -- FTS & FTC
    COUNT(CASE WHEN fts_month           = DATE_TRUNC('month', CURRENT_DATE())                     AND fts_bd           <= (SELECT bd FROM today_bd) THEN 1 END) AS fts_cur,
    COUNT(CASE WHEN fts_month           = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND fts_bd           <= (SELECT bd FROM today_bd) THEN 1 END) AS fts_prev,
    COUNT(CASE WHEN ftc_month           = DATE_TRUNC('month', CURRENT_DATE())                     AND ftc_bd           <= (SELECT bd FROM today_bd) THEN 1 END) AS ftc_cur,
    COUNT(CASE WHEN ftc_month           = DATE_TRUNC('month', DATEADD('month',-1,CURRENT_DATE())) AND ftc_bd           <= (SELECT bd FROM today_bd) THEN 1 END) AS ftc_prev,
    -- MQL (Real Business) by grade
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
    -- CVR weekly windows
    COUNT(CASE WHEN DATE_TRUNC('week', registration_datetime::DATE) = DATE_TRUNC('week', DATEADD('day', -7,CURRENT_DATE()))  THEN 1 END) AS cvr_reg_w1,
    COUNT(CASE WHEN DATE_TRUNC('week', registration_datetime::DATE) = DATE_TRUNC('week', DATEADD('day', -7,CURRENT_DATE()))  AND melio_fts IS NOT NULL AND DATEDIFF('day', registration_datetime::DATE, melio_fts::DATE) BETWEEN 0 AND 7 THEN 1 END) AS cvr_fts_w1,
    COUNT(CASE WHEN DATE_TRUNC('week', registration_datetime::DATE) = DATE_TRUNC('week', DATEADD('day',-14,CURRENT_DATE())) THEN 1 END) AS cvr_reg_w2,
    COUNT(CASE WHEN DATE_TRUNC('week', registration_datetime::DATE) = DATE_TRUNC('week', DATEADD('day',-14,CURRENT_DATE())) AND melio_fts IS NOT NULL AND DATEDIFF('day', registration_datetime::DATE, melio_fts::DATE) BETWEEN 0 AND 7 THEN 1 END) AS cvr_fts_w2
FROM with_bd
GROUP BY source_type
ORDER BY act_total_cur DESC
