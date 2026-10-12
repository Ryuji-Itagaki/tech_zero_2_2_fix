-- =========================================================
-- Tech0 2_2 営業情報 検索・活用App  表の定義
-- 項目の正は「techzero2_2スキーマ定義.csv」。
-- 何度実行しても壊れない（IF NOT EXISTS）。
-- 作る順番：他の表から参照される表を先に作る。
-- =========================================================

PRAGMA foreign_keys = ON;

-- ---------- 外部データ（行内の上流DB・公的データ） ----------

-- 市区町村マスタ（デジタル庁 アドレス・ベース・レジストリ）
CREATE TABLE IF NOT EXISTS master_city (
    city_code            TEXT PRIMARY KEY,   -- 市区町村コード
    prefecture_name      TEXT NOT NULL,      -- 都道府県名
    city_name            TEXT NOT NULL,      -- 市区町村名
    designated_city_name TEXT,               -- 政令市名（区のときだけ）
    display_name         TEXT NOT NULL       -- 表示名：中央区（福岡市）
);

-- 企業マスタ（帝国データバンク等を取り込んだもの。デモはダミー）
CREATE TABLE IF NOT EXISTS master_company (
    company_id       INTEGER PRIMARY KEY,    -- 企業ID（行内共通）
    tdb_code         TEXT NOT NULL UNIQUE,   -- 帝国データバンク企業コード
    corporate_number TEXT UNIQUE,            -- 法人番号（個人事業主は空）
    company_name     TEXT NOT NULL,          -- 法人名・個人事業主名
    industry         TEXT,                   -- 業種
    established      INTEGER,                -- 設立年
    address          TEXT,                   -- 所在地
    city_code        TEXT REFERENCES master_city(city_code),  -- 市区町村コード
    updated_on       TEXT                    -- 情報の更新日
);

-- 企業の年度別数値（帝国データバンク。デモはダミー）
CREATE TABLE IF NOT EXISTS company_financials (
    company_id     INTEGER NOT NULL REFERENCES master_company(company_id),  -- 企業ID
    fiscal_year    INTEGER NOT NULL,         -- 年度
    sales_man_yen  INTEGER,                  -- 売上高（万円）
    profit_man_yen INTEGER,                  -- 経常利益（万円）
    employees      INTEGER,                  -- 従業員数
    score          INTEGER,                  -- 評点
    PRIMARY KEY (company_id, fiscal_year)
);

-- gBizINFO企業情報（経済産業省。法人番号でつなぐ）
CREATE TABLE IF NOT EXISTS master_gbizinfo (
    corporate_number TEXT PRIMARY KEY,       -- 法人番号
    capital_yen      INTEGER,                -- 資本金（円）
    updated_on       TEXT                    -- 情報の更新日
);

-- ---------- 行内データ（行員が日ごろ入れているもの） ----------

-- 担当者
CREATE TABLE IF NOT EXISTS staff (
    id          INTEGER PRIMARY KEY,         -- 担当者ID
    name        TEXT NOT NULL,               -- 氏名
    branch_code TEXT,                        -- 所属店の店番
    role        TEXT NOT NULL                -- 担当／本部
);

-- 取引先（企業マスタにある会社＝当行の取引先）
CREATE TABLE IF NOT EXISTS customers (
    id                 INTEGER PRIMARY KEY,  -- 取引先ID
    name               TEXT NOT NULL,        -- 取引先名
    branch_code        TEXT,                 -- 店番
    branch_name        TEXT,                 -- 営業店名
    block_name         TEXT,                 -- ブロック名
    union_branch_name  TEXT,                 -- 連合店名
    branch_customer_no INTEGER,              -- 店別顧客番号
    staff_id           INTEGER REFERENCES staff(id),  -- 主担当
    company_id         INTEGER NOT NULL REFERENCES master_company(company_id)  -- 企業ID
);

-- 接触履歴（＝「相談」）
CREATE TABLE IF NOT EXISTS contact_logs (
    id           INTEGER PRIMARY KEY,        -- 接触履歴ID
    contact_date TEXT NOT NULL,              -- 接触した日
    start_time   TEXT,                       -- 開始時刻
    end_time     TEXT,                       -- 終了時刻
    customer_id  INTEGER NOT NULL REFERENCES customers(id),  -- 取引先ID
    staff_id     INTEGER NOT NULL REFERENCES staff(id),      -- 対応した担当者ID
    purpose      TEXT NOT NULL,              -- 接触目的
    method       TEXT,                       -- 接触方法
    partner      TEXT,                       -- 接触相手
    content      TEXT,                       -- 内容
    reaction     TEXT,                       -- 顧客の反応
    next_action  TEXT,                       -- 次回アクション
    next_date    TEXT                        -- 次回予定日
);

-- 案件（＝「決定」。融資案件）
CREATE TABLE IF NOT EXISTS deals (
    id               INTEGER PRIMARY KEY,    -- 案件ID
    deal_no          TEXT NOT NULL UNIQUE,   -- 案件番号
    deal_type        TEXT NOT NULL,          -- 案件種別
    deal_name        TEXT NOT NULL,          -- 案件名
    customer_id      INTEGER NOT NULL REFERENCES customers(id),  -- 取引先ID
    staff_id         INTEGER NOT NULL REFERENCES staff(id),      -- 担当者ID
    received_date    TEXT,                   -- 受付日
    answer_due_date  TEXT,                   -- 回答予定日
    status           TEXT NOT NULL,          -- 状況（処理中／実行済／取下／謝絶）
    amount_yen       INTEGER,                -- 申込金額（円）
    background       TEXT,                   -- 取組の経緯
    situation        TEXT,                   -- 案件状況
    decline_reason   TEXT,                   -- 謝絶理由
    withdraw_reason1 TEXT,                   -- 取下理由1
    withdraw_reason2 TEXT,                   -- 取下理由2
    withdraw_reason3 TEXT,                   -- 取下理由3
    note_branch      TEXT,                   -- 特記事項（営業店）
    note_hq          TEXT,                   -- 特記事項（本部）
    updated_by       TEXT,                   -- 最終更新者
    updated_at       TEXT                    -- 最終更新日時
);

-- ---------- 検索を速くするための索引 ----------
CREATE INDEX IF NOT EXISTS idx_customers_company   ON customers(company_id);
CREATE INDEX IF NOT EXISTS idx_company_city        ON master_company(city_code);
CREATE INDEX IF NOT EXISTS idx_company_industry    ON master_company(industry);
CREATE INDEX IF NOT EXISTS idx_logs_customer_date  ON contact_logs(customer_id, contact_date);
CREATE INDEX IF NOT EXISTS idx_logs_purpose        ON contact_logs(purpose);
CREATE INDEX IF NOT EXISTS idx_deals_customer_date ON deals(customer_id, received_date);

-- ---------- ビュー（読み出し専用の「見え方」。データは持たない） ----------

-- 企業の顔ぶれ：企業マスタ＋最新年度の数値＋資本金＋市区町村の表示名
DROP VIEW IF EXISTS v_company_profile;
CREATE VIEW v_company_profile AS
SELECT
    m.company_id,
    m.tdb_code,
    m.corporate_number,
    m.company_name,
    m.industry,
    m.established,
    m.address,
    m.city_code,
    c.display_name   AS city_display_name,
    c.prefecture_name,
    f.fiscal_year    AS latest_fiscal_year,
    f.sales_man_yen,
    f.profit_man_yen,
    f.employees,
    f.score,
    g.capital_yen
FROM master_company m
LEFT JOIN master_city c ON c.city_code = m.city_code
LEFT JOIN company_financials f
       ON f.company_id = m.company_id
      AND f.fiscal_year = (SELECT MAX(fiscal_year) FROM company_financials
                           WHERE company_id = m.company_id)
LEFT JOIN master_gbizinfo g ON g.corporate_number = m.corporate_number;

-- 記録の一覧：接触履歴（相談）と案件（決定）を同じ形に並べ、企業データを付けたもの。
-- search_text はキーワード検索・文章の似ている度合いの対象
-- （接触履歴：内容・反応・次回アクション／案件：経緯・状況）。
DROP VIEW IF EXISTS v_records;
CREATE VIEW v_records AS
SELECT
    '相談'            AS record_type,
    'C-' || l.id      AS record_key,
    l.id              AS source_id,
    l.customer_id,
    cu.name           AS customer_name,
    l.staff_id,
    s.name            AS staff_name,
    l.contact_date    AS record_date,
    l.purpose,
    NULL              AS deal_type,
    NULL              AS deal_name,
    l.method,
    l.partner,
    l.content,
    l.reaction,
    l.next_action,
    NULL              AS status,
    NULL              AS amount_yen,
    NULL              AS decline_reason,
    NULL              AS withdraw_reasons,
    TRIM(COALESCE(l.content, '') || ' ' || COALESCE(l.reaction, '') || ' '
         || COALESCE(l.next_action, '')) AS search_text,
    p.company_id, p.industry, p.city_code, p.city_display_name,
    p.sales_man_yen, p.employees, p.score
FROM contact_logs l
JOIN customers cu        ON cu.id = l.customer_id
LEFT JOIN staff s        ON s.id = l.staff_id
JOIN v_company_profile p ON p.company_id = cu.company_id
UNION ALL
SELECT
    '決定'            AS record_type,
    'D-' || d.id      AS record_key,
    d.id              AS source_id,
    d.customer_id,
    cu.name           AS customer_name,
    d.staff_id,
    s.name            AS staff_name,
    d.received_date   AS record_date,
    NULL              AS purpose,
    d.deal_type,
    d.deal_name,
    NULL              AS method,
    NULL              AS partner,
    d.background      AS content,
    NULL              AS reaction,
    NULL              AS next_action,
    d.status,
    d.amount_yen,
    d.decline_reason,
    TRIM(COALESCE(d.withdraw_reason1, '') || ' ' || COALESCE(d.withdraw_reason2, '')
         || ' ' || COALESCE(d.withdraw_reason3, '')) AS withdraw_reasons,
    TRIM(COALESCE(d.deal_name, '') || ' ' || COALESCE(d.background, '') || ' '
         || COALESCE(d.situation, '')) AS search_text,
    p.company_id, p.industry, p.city_code, p.city_display_name,
    p.sales_man_yen, p.employees, p.score
FROM deals d
JOIN customers cu        ON cu.id = d.customer_id
LEFT JOIN staff s        ON s.id = d.staff_id
JOIN v_company_profile p ON p.company_id = cu.company_id;
