"""add_demo_companies.py — デモ用に「規模の違う同業」を data/*.csv に足す（10/11 追加）

目的：パン屋を検索したとき、同じ「製パン・菓子製造」でも規模が違う会社（パン工場・大手メーカーの宮崎工場）が
      低いスコアで出ることを見せる。がっきーのCSV（8表）に行を追加するだけで、既存の行は変えない。

実行:  python add_demo_companies.py   （何度実行しても二重には入らない）
その後: python import_data.py
"""
import csv
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

# ---- 追加する会社（company_id は既存の最大値 1470 の続き） -------------------------------
#  (company_id, tdb_code, corporate_number, 会社名, 業種, 設立, 住所, 市区町村コード,
#   売上高(万円), 経常利益(万円), 従業員, 評点, 資本金(円), 取引先ID, 店番, 営業店, 主担当staff_id)
COMPANIES = [
    (1471, "900000471", "1000000000471", "有限会社鈴蘭ベーカリー",            "製パン・菓子製造", 2010, "福岡県福岡市博多区美野島2-4-1",   "401323",   7800,   62,   8, 51,    5000000, 1501, "003", "港南支店", 12),
    (1472, "900000472", "1000000000472", "博多パン工業株式会社",              "製パン・菓子製造", 1988, "福岡県福岡市東区箱崎ふ頭5-2-3",  "401315",  28000,  900,  32, 56,   20000000, 1502, "003", "港南支店", 11),
    (1473, "900000473", "1000000000473", "九州フレッシュベーカリー株式会社 糸島工場", "製パン・菓子製造", 1995, "福岡県糸島市前原西1-10-5",   "402303",  95000, 3200,  85, 60,   50000000, 1503, "004", "駅前支店", 13),
    (1474, "900000474", "1000000000474", "日ノ本製パン株式会社 宮崎工場",      "製パン・菓子製造", 1962, "宮崎県宮崎市佐土原町下田島2-1", "452017", 1250000, 42000, 480, 68, 1000000000, 1504, "001", "本店営業部", 3),
    (1475, "900000475", "1000000000475", "西日本ブレッド株式会社 福岡工場",     "製パン・菓子製造", 1975, "福岡県北九州市八幡東区東田3-1-2", "401081", 460000, 15000, 210, 63,  300000000, 1505, "001", "本店営業部", 3),
]

# ---- 追加する接触履歴（相談）・案件（決定） ------------------------------------------------
LOGS = [  # (取引先ID, staff_id, 日付, 目的, 方法, 相手, 内容, 反応, 次回アクション, 次回予定日)
    (1501, 12, "2025-10-07", "ビジネスマッチング", "訪問", "代表者", "イベント出店の販路を探している。地元の商業施設を紹介", "前向き。商談を希望", "紹介先と日程調整", "2025-10-21"),
    (1501, 12, "2026-03-04", "新規貸出", "訪問", "代表者", "2号店の開業資金600万円を提案。立地は博多駅周辺で検討中", "前向き。事業計画を作成中", "事業計画受領後に審査へ", "2026-04-10"),
    (1502, 11, "2025-11-18", "プロパー融資", "訪問", "部長・課長", "製造ラインの自動化設備に伴う設備資金4,000万円の相談。人手不足への対応", "前向き。補助金との併用を検討", "補助金の要件を確認し再訪", "2025-12-05"),
    (1502, 11, "2026-02-12", "事業承継提案", "訪問", "代表者", "社長67歳。長男が工場長として勤務。親族内承継の進め方を相談", "関心あり。株価評価を知りたい", "承継計画の支援を案内", "2026-03-01"),
    (1503, 13, "2025-09-25", "プロパー融資", "訪問", "役員", "冷凍生地ラインの増設に伴う設備資金1.2億円の相談。県外スーパー向けの受注増", "前向き。他行とも比較", "金利条件を提示", "2025-10-15"),
    (1503, 13, "2026-01-20", "ビジネスマッチング", "訪問", "部長・課長", "原材料（小麦粉）の仕入先を複線化したい。県内の製粉会社を紹介", "助かるとのこと", "紹介後に状況確認", "2026-02-10"),
    (1504,  3, "2025-07-15", "プロパー融資", "訪問", "役員", "宮崎工場の生産ライン更新に伴う設備資金8億円のシンジケートローン参加の打診", "前向き。主幹事行と調整中", "本部融資部と連携", "2025-08-01"),
    (1504,  3, "2026-04-08", "外為関連", "訪問", "部長・課長", "輸入小麦の為替予約について相談。年間の為替ヘッジ方針を聞き取り", "情報収集の段階", "市場部と同行訪問", "2026-05-12"),
    (1505,  3, "2025-12-02", "プロパー融資", "訪問", "役員", "福岡工場の省エネ設備（ボイラー更新）の設備資金2億円の相談。GX関連補助金の活用も検討", "前向き", "補助金申請の支援を案内", "2026-01-15"),
]
DEALS = [  # (取引先ID, staff_id, 種別, 案件名, 受付日, 回答予定日, 状況, 申込金額(円), 経緯, 案件状況, 謝絶理由, 取下理由1)
    (1501, 12, "融資", "開業資金（2号店）",          "2026-03-10", "2026-03-24", "処理中", 6000000,   "2026-03-04の面談で2号店の開業資金の相談を受けた", "審査中", "", ""),
    (1502, 11, "融資", "設備資金（製造ライン自動化）", "2025-11-25", "2025-12-09", "実行済", 40000000,  "2025-11-18の面談で自動化設備の相談を受けた", "実行済。補助金と併用", "", ""),
    (1503, 13, "融資", "設備資金（冷凍生地ライン増設）", "2025-10-02", "2025-10-16", "実行済", 120000000, "2025-09-25の面談で設備資金の相談を受けた", "実行済", "", ""),
    (1504,  3, "融資", "設備資金（宮崎工場ライン更新・シンジケート）", "2025-07-22", "2025-08-05", "謝絶", 800000000, "2025-07-15に主幹事行からシンジケートローン参加の打診", "謝絶", "与信枠超過のため参加見送り", ""),
    (1505,  3, "融資", "設備資金（省エネボイラー）",   "2025-12-09", "2025-12-23", "実行済", 200000000, "2025-12-02の面談で省エネ設備の相談を受けた", "実行済", "", ""),
]


def _append(name, rows, key_col, key_vals=None):
    """key_col: 1列名か、列名のタプル（組み合わせで重複判定）"""
    keys = key_col if isinstance(key_col, tuple) else (key_col,)
    k = lambda r: tuple(str(r[c]) for c in keys)
    path = DATA / f"{name}.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        existing = {k(r) for r in reader}
    new = [r for r in rows if k(r) not in existing]
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        for r in new:
            w.writerow({k: r.get(k, "") for k in fields})
    print(f"{name}.csv  +{len(new)}件")


def main():
    # 既存の最大IDを読む
    def max_id(name, col="id"):
        with (DATA / f"{name}.csv").open(encoding="utf-8-sig", newline="") as f:
            return max(int(r[col]) for r in csv.DictReader(f))
    log_id, deal_id = max_id("contact_logs"), max_id("deals")

    _append("master_company", [dict(company_id=c[0], tdb_code=c[1], corporate_number=c[2], company_name=c[3], industry=c[4],
                                    established=c[5], address=c[6], city_code=c[7], updated_on="2026-04-01") for c in COMPANIES],
            "company_id")
    fin = []
    for c in COMPANIES:
        for y, k in ((2023, 0.93), (2024, 0.97), (2025, 1.0)):
            fin.append(dict(company_id=c[0], fiscal_year=y, sales_man_yen=int(c[8] * k), profit_man_yen=int(c[9] * k),
                            employees=int(round(c[10] * (0.95 if y < 2025 else 1))), score=c[11]))
    # company_financials は (company_id, fiscal_year) が主キー
    path = DATA / "company_financials.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f); fields = reader.fieldnames
        existing = {(r["company_id"], r["fiscal_year"]) for r in reader}
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); n = 0
        for r in fin:
            if (str(r["company_id"]), str(r["fiscal_year"])) not in existing:
                w.writerow(r); n += 1
    print(f"company_financials.csv  +{n}件")
    _append("master_gbizinfo", [dict(corporate_number=c[2], capital_yen=c[12], updated_on="2026-03-31") for c in COMPANIES],
            "corporate_number")
    _append("customers", [dict(id=c[13], name=c[3], branch_code=c[14], branch_name=c[15], block_name="東ブロック",
                               union_branch_name=c[15].replace("支店", "連合").replace("営業部", "連合"),
                               branch_customer_no=c[13], staff_id=c[16], company_id=c[0]) for c in COMPANIES], "id")
    _append("contact_logs", [dict(id=log_id + i + 1, contact_date=l[2], start_time="10:00", end_time="11:00", customer_id=l[0],
                                  staff_id=l[1], purpose=l[3], method=l[4], partner=l[5], content=l[6], reaction=l[7],
                                  next_action=l[8], next_date=l[9]) for i, l in enumerate(LOGS)], ("customer_id", "contact_date", "purpose"))
    _append("deals", [dict(id=deal_id + i + 1, deal_no=f"ANK-{deal_id + i + 1:05d}", deal_type=d[2], deal_name=d[3], customer_id=d[0],
                           staff_id=d[1], received_date=d[4], answer_due_date=d[5], status=d[6], amount_yen=d[7], background=d[8],
                           situation=d[9], decline_reason=d[10], withdraw_reason1=d[11], withdraw_reason2="", withdraw_reason3="",
                           note_branch="", note_hq="", updated_by="システム連携", updated_at=d[4] + " 17:00:00")
                      for i, d in enumerate(DEALS)], ("customer_id", "deal_name"))


if __name__ == "__main__":
    main()
