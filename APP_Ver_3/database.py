"""
database.py — DBの読み書き（担当：がっきー）

他のファイル（app.py / ranking.py）は、DBに直接つながず、必ずここの関数を通してデータを取る。
戻り値はすべて「辞書のリスト」（1件なら辞書、見つからなければ None）。

  じんじん（app.py）が使う：
    search_customers / get_customer / get_contact_logs / get_deals / search_records
    画面の選択肢用：list_cities / list_industries / list_purposes
  ちか（ranking.py）が使う：
    get_all_records / search_records

記録（get_all_records・search_records が返す1件）の主な項目：
    record_type   "相談"（接触履歴）か "決定"（案件）
    record_key    "C-123" / "D-45" のような一意のキー
    customer_id, customer_name, staff_name, record_date
    purpose       接触目的（決定のときは None）
    deal_type, deal_name, status, amount_yen, decline_reason, withdraw_reasons（決定のときだけ）
    content, reaction, next_action（相談のときだけ。決定の content は取組の経緯）
    search_text   キーワード検索・文章の似ている度合いに使う文章
    company_id, industry, city_code, city_display_name, sales_man_yen, employees, score
"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "app.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


# ---------------------------------------------------------------
# 接続・初期化
# ---------------------------------------------------------------
def get_connection():
    """DBへの接続を返す。行は辞書のように扱える。data/ がなければ作る。"""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """schema.sql を実行して表・ビューを作る（何度実行してもよい）。"""
    conn = get_connection()
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def _fetch_all(sql, params=()):
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _fetch_one(sql, params=()):
    rows = _fetch_all(sql, params)
    return rows[0] if rows else None


# ---------------------------------------------------------------
# 取引先
# ---------------------------------------------------------------
def search_customers(name_part, limit=50):
    """
    取引先名の一部で検索する。
    返すもの：[{id, name, branch_name, industry, city_display_name}, ...]（名前順）
    """
    name_part = (name_part or "").strip()
    if not name_part:
        return []
    return _fetch_all(
        """
        SELECT cu.id, cu.name, cu.branch_name,
               p.industry, p.city_display_name
        FROM customers cu
        JOIN v_company_profile p ON p.company_id = cu.company_id
        WHERE cu.name LIKE ?
        ORDER BY cu.name
        LIMIT ?
        """,
        (f"%{name_part}%", limit),
    )


def get_customer(customer_id):
    """
    取引先の情報＋企業データ（業種・最新年度の売上・従業員数・評点・資本金・市区町村）。
    見つからなければ None。
    """
    return _fetch_one(
        """
        SELECT cu.id, cu.name, cu.branch_code, cu.branch_name, cu.block_name,
               cu.union_branch_name, cu.branch_customer_no,
               cu.staff_id, s.name AS staff_name,
               p.*
        FROM customers cu
        LEFT JOIN staff s ON s.id = cu.staff_id
        JOIN v_company_profile p ON p.company_id = cu.company_id
        WHERE cu.id = ?
        """,
        (customer_id,),
    )


def get_contact_logs(customer_id):
    """その会社の接触履歴（新しい順）。担当者名付き。"""
    return _fetch_all(
        """
        SELECT l.*, s.name AS staff_name
        FROM contact_logs l
        LEFT JOIN staff s ON s.id = l.staff_id
        WHERE l.customer_id = ?
        ORDER BY l.contact_date DESC, l.start_time DESC
        """,
        (customer_id,),
    )


def get_deals(customer_id):
    """その会社の案件一覧（受付日の新しい順）。担当者名付き。"""
    return _fetch_all(
        """
        SELECT d.*, s.name AS staff_name
        FROM deals d
        LEFT JOIN staff s ON s.id = d.staff_id
        WHERE d.customer_id = ?
        ORDER BY d.received_date DESC
        """,
        (customer_id,),
    )


# ---------------------------------------------------------------
# 記録（接触履歴＋案件）
# ---------------------------------------------------------------
def get_all_records():
    """全社分の接触履歴・案件を、企業データ付きで返す（日付の新しい順）。"""
    return _fetch_all("SELECT * FROM v_records ORDER BY record_date DESC")


def search_records(company_name=None, keyword=None, city_code=None,
                   industry=None, record_type=None, purpose=None, limit=None):
    """
    6つの入口で記録を絞り込む。どれも任意で、入れた条件をすべて満たす記録を返す。
    並べ替えはしない（日付の新しい順で返す）。関連の深い順は ranking.py で行う。

      company_name : 取引先名の一部
      keyword      : 自由入力。空白で区切った語をすべて含む記録に絞る
      city_code    : 市区町村コード（list_cities の city_code）
      industry     : 業種（list_industries の値）
      record_type  : "相談"（接触履歴）／"決定"（案件）
      purpose      : 接触目的（list_purposes の値）
                     ※案件には接触目的がないため、指定すると相談だけが返る（未決事項・仮置き）
    何も入れなければ全件を新しい順に返す。
    """
    where, params = [], []

    if company_name and company_name.strip():
        where.append("customer_name LIKE ?")
        params.append(f"%{company_name.strip()}%")
    if keyword and keyword.strip():
        for word in keyword.replace("　", " ").split():
            where.append("search_text LIKE ?")
            params.append(f"%{word}%")
    if city_code:
        where.append("city_code = ?")
        params.append(str(city_code))
    if industry:
        where.append("industry = ?")
        params.append(industry)
    if record_type in ("相談", "決定"):
        where.append("record_type = ?")
        params.append(record_type)
    if purpose:
        where.append("purpose = ?")
        params.append(purpose)

    sql = "SELECT * FROM v_records"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY record_date DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    return _fetch_all(sql, params)


# ---------------------------------------------------------------
# 画面の選択肢
# ---------------------------------------------------------------
def list_cities():
    """取引先がいる市区町村だけ。[{city_code, display_name, prefecture_name}]"""
    return _fetch_all(
        """
        SELECT DISTINCT c.city_code, c.display_name, c.prefecture_name
        FROM master_city c
        JOIN master_company m ON m.city_code = c.city_code
        ORDER BY c.city_code
        """
    )


def list_industries():
    """業種の一覧（企業マスタにあるもの）。"""
    return [r["industry"] for r in _fetch_all(
        "SELECT DISTINCT industry FROM master_company "
        "WHERE industry IS NOT NULL ORDER BY industry")]


def list_purposes():
    """接触目的の一覧（データにあるもの）。32種の正式リストができたら差し替える。"""
    return [r["purpose"] for r in _fetch_all(
        "SELECT DISTINCT purpose FROM contact_logs ORDER BY purpose")]


# 動作確認：python database.py
if __name__ == "__main__":
    init_db()
    hits = search_customers("ベーカリー")
    print(f"search_customers('ベーカリー') → {len(hits)}件", hits[:2])
    if hits:
        cid = hits[0]["id"]
        print("get_customer →", get_customer(cid))
        print("get_contact_logs →", len(get_contact_logs(cid)), "件")
        print("get_deals →", len(get_deals(cid)), "件")
    print("get_all_records →", len(get_all_records()), "件")
    print("search_records(業種=製パン・菓子製造, 決定) →",
          len(search_records(industry="製パン・菓子製造", record_type="決定")), "件")


# ---------------------------------------------------------------
# 10/11 追加（じんじん）：類似企業スコアリング用
# ---------------------------------------------------------------
def get_company_profiles(industry=None):
    """
    当行の取引先になっている会社の顔ぶれ（企業データ付き）。業種を指定すればその業種だけ。
    返すもの：[{customer_id, customer_name, branch_name, company_id, industry, sales_man_yen, employees,
               capital_yen, score, city_display_name, established}, ...]
    """
    sql = """
        SELECT cu.id AS customer_id, cu.name AS customer_name, cu.branch_name,
               p.company_id, p.industry, p.sales_man_yen, p.employees, p.capital_yen, p.score,
               p.city_display_name, p.established
        FROM customers cu
        JOIN v_company_profile p ON p.company_id = cu.company_id
    """
    params = ()
    if industry:
        sql += " WHERE p.industry = ?"
        params = (industry,)
    return _fetch_all(sql + " ORDER BY cu.name", params)


def get_latest_contact(customer_id):
    """最後に会った日・担当者・目的（なければ None）"""
    return _fetch_one(
        """
        SELECT l.contact_date, l.purpose, l.content, s.name AS staff_name
        FROM contact_logs l LEFT JOIN staff s ON s.id = l.staff_id
        WHERE l.customer_id = ? ORDER BY l.contact_date DESC, l.id DESC LIMIT 1
        """, (customer_id,))
