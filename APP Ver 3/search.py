"""
search.py — 画面から呼ぶ検索処理（担当：じんじん）

役割分担
  ranking.py (ちか)   : 企業規模の類似度スコア（売上高50・従業員数30・資本金20）。ここでは一切変更せずに呼ぶだけ。
  database.py (がっきー): 8表の読み出し。
  search.py (じんじん): 上の2つをつないで、画面が使う形（DataFrame）にする。
                        ・類似企業：同業種をマスト条件にして ranking.py の点数で並べる
                        ・キーワード検索：記録（相談・決定）を文章の近さで探し、基準の会社があれば規模スコアで並べ替える
                        ・タグ：記録の種類・目的・状況・本文のキーワードから自動で付ける（入力は増やさない）
"""
from collections import OrderedDict

import pandas as pd

import database as db
import ranking as rk

# ---- 類似企業 ----------------------------------------------------------------------------
METRIC_LABELS = OrderedDict([
    ("sales_man_yen", ("売上高", "sales_score", rk.WEIGHTS["sales_man_yen"])),
    ("employees",     ("従業員数", "employees_score", rk.WEIGHTS["employees"])),
    ("capital_yen",   ("資本金", "capital_score", rk.WEIGHTS["capital_yen"])),
])


def _customer_index(industry=None):
    """company_id → 取引先の情報（customer_id・支店・市区町村 など）"""
    return {p["company_id"]: p for p in db.get_company_profiles(industry=industry)}


def similar_companies(customer_id):
    """
    検索した会社と同じ業種の取引先を、ranking.py の規模スコアの高い順に返す。
    返すもの：DataFrame[rank, customer_id, customer_name, branch_name, city_display_name,
                       sales_man_yen, employees, capital_yen, total_score, sales_score, employees_score,
                       capital_score, missing_fields]
    """
    base = db.get_customer(customer_id)
    if base is None:
        return pd.DataFrame()
    cust = _customer_index(industry=base["industry"])
    ranked = rk.rank_companies(base["company_id"], candidate_ids=cust.keys(), same_industry=True)
    rows = []
    for r in ranked:
        c = cust.get(r["company_id"])
        if c is None or c["customer_id"] == customer_id:
            continue
        rows.append({
            "customer_id": c["customer_id"], "customer_name": c["customer_name"],
            "branch_name": c["branch_name"], "city_display_name": c["city_display_name"],
            "sales_man_yen": r["sales_man_yen"], "employees": r["employees"], "capital_yen": r["capital_yen"],
            "total_score": r["total_score"], "sales_score": r["sales_score"],
            "employees_score": r["employees_score"], "capital_score": r["capital_score"],
            "missing_fields": r["missing_fields"],
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df.insert(0, "rank", range(1, len(df) + 1))
    return df


def score_breakdown(base, row):
    """内訳表の行：[{指標, 配点, 基準の会社, この会社, 得点}]"""
    out = []
    for col, (label, score_col, pts) in METRIC_LABELS.items():
        out.append({"指標": label, "配点": pts, "基準の会社": base.get(col), "この会社": row.get(col),
                    "得点": row.get(score_col, 0)})
    return out


# ---- タグ --------------------------------------------------------------------------------
NEED_TAGS = OrderedDict([
    ("事業承継",   ["事業承継", "承継", "後継", "株価評価", "親族内"]),
    ("M&A",       ["M&A", "Ｍ＆Ａ", "買収", "譲渡", "売却"]),
    ("運転資金",   ["運転資金", "資金繰り", "つなぎ", "賞与資金", "季節資金"]),
    ("設備資金",   ["設備資金", "設備投資", "ライン", "機械", "工場", "改装", "車両"]),
    ("創業・開業", ["創業", "開業", "新規出店", "2号店", "２号店", "新店"]),
    ("借換",       ["借換", "借り換え", "肩代わり", "他行"]),
    ("条件変更",   ["条件変更", "リスケ", "返済猶予", "据置"]),
    ("補助金",     ["補助金", "助成金", "GX", "省エネ"]),
    ("販路・紹介", ["ビジネスマッチング", "販路", "紹介", "仕入先", "取引先開拓"]),
    ("人手不足",   ["人手不足", "採用", "自動化", "省力化", "人材"]),
    ("外為",       ["外為", "為替", "輸入", "輸出"]),
    ("相続・資産", ["相続", "遺言", "資産運用", "個人資産"]),
])


def tags_for(rec):
    tags = [rec.get("record_type") or ""]
    if rec.get("purpose"):
        tags.append(rec["purpose"])
    if rec.get("status"):
        tags.append(rec["status"])
    text = " ".join(str(rec.get(k) or "") for k in ("search_text", "purpose", "deal_name", "decline_reason"))
    for tag, words in NEED_TAGS.items():
        if any(w in text for w in words):
            tags.append(tag)
    return [t for t in tags if t]


# ---- キーワード検索 -----------------------------------------------------------------------
MAX_QUERY_LEN = 50          # 入力の上限（長すぎる検索語は受け付けない）
MAX_ROWS = 3000             # 文章の近さを計算する記録の上限（新しい順に残す）


def clean_query(q):
    q = (q or "").replace("　", " ").strip()
    return q[:MAX_QUERY_LEN]


def _relevance(texts, query):
    """検索語と文章の近さ 0〜1（文字 2〜3-gram の TF-IDF × コサイン類似度）。scikit-learn が無ければ語の出現数。"""
    if not texts:
        return []
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3))
        X = vec.fit_transform(list(texts) + [query])
        sims = cosine_similarity(X[-1], X[:-1]).ravel()
        mx = sims.max() if len(sims) else 0
        return list(sims / mx) if mx > 0 else [0.0] * len(texts)
    except Exception:
        words = query.split()
        return [sum(t.count(w) for w in words) / max(1, len(words)) for t in texts]


def search_keyword(keyword, base_customer_id=None, industry=None, city_code=None,
                   record_type=None, one_per_company=True):
    """
    キーワード検索（空白区切りで AND）。
      base_customer_id あり → その会社の業種をマストにし、総合 = 規模スコア 70% ＋ 文章の近さ 30%
      なし                 → こだわり条件で絞り、文章の近さ 100%
    返すもの：DataFrame（v_records の列 ＋ relevance, size_score, total, tags）
    """
    keyword = clean_query(keyword)
    if not keyword:
        return pd.DataFrame()
    base = db.get_customer(base_customer_id) if base_customer_id else None
    if base:
        industry = base["industry"]
    recs = db.search_records(keyword=keyword, industry=industry, city_code=city_code, record_type=record_type)
    if base:
        recs = [r for r in recs if r["customer_id"] != base["id"]]
    recs = recs[:MAX_ROWS]
    if not recs:
        return pd.DataFrame()

    df = pd.DataFrame(recs)
    df["relevance"] = _relevance(
        (df["search_text"].fillna("") + " " + df["purpose"].fillna("") + " " + df["deal_name"].fillna("")).tolist(),
        keyword)
    df["tags"] = [tags_for(r) for r in recs]

    if base:
        companies = rk.load_companies()
        b = companies.get(base["company_id"], {})
        scores = {}
        for cid in df["company_id"].unique():
            o = companies.get(cid)
            scores[cid] = rk.score_company(b, o)["total_score"] if (b and o) else 0.0
        df["size_score"] = df["company_id"].map(scores)
        df["total"] = (df["size_score"] * 0.7 + df["relevance"] * 100 * 0.3).round(1)
    else:
        df["size_score"] = None
        df["total"] = (df["relevance"] * 100).round(1)

    df = df.sort_values(["total", "record_date"], ascending=[False, False])
    if one_per_company:
        df = df.drop_duplicates("customer_id", keep="first")
    df = df.reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


# ---- タグで絞り込み・並べ替え -------------------------------------------------------------
def all_tags(df):
    if df is None or df.empty or "tags" not in df:
        return []
    cnt = {}
    for ts in df["tags"]:
        for t in ts:
            cnt[t] = cnt.get(t, 0) + 1
    return sorted(cnt.items(), key=lambda x: (-x[1], x[0]))


def filter_by_tags(df, tags, mode="all"):
    if not tags or df is None or df.empty:
        return df
    f = (lambda ts: all(t in ts for t in tags)) if mode == "all" else (lambda ts: any(t in ts for t in tags))
    return df[df["tags"].apply(f)].reset_index(drop=True)


SORT_KEYS = {
    "総合スコア順":   ("total", False),
    "規模の近い順":   ("size_score", False),
    "文章の近い順":   ("relevance", False),
    "新しい順":       ("record_date", False),
    "古い順":         ("record_date", True),
    "金額の大きい順": ("amount_yen", False),
}


def sort_results(df, key="総合スコア順"):
    col, asc = SORT_KEYS.get(key, ("total", False))
    if df is None or df.empty or col not in df or df[col].isna().all():
        return df
    out = df.sort_values(col, ascending=asc, na_position="last").reset_index(drop=True)
    out["rank"] = range(1, len(out) + 1)
    return out


if __name__ == "__main__":
    cid = db.search_customers("こむぎ堂")[0]["id"]
    sim = similar_companies(cid)
    print(f"類似企業 {len(sim)} 社")
    print(sim[["rank", "customer_name", "sales_man_yen", "employees", "capital_yen", "total_score"]].head(5).to_string(index=False))
    print(sim[sim["customer_name"].str.contains("工場|パン工業")][["rank", "customer_name", "total_score"]].to_string(index=False))
    r = search_keyword("事業承継", base_customer_id=cid)
    print(f"\nキーワード『事業承継』: {len(r)} 社")
    print(r[["rank", "customer_name", "record_date", "size_score", "relevance", "total", "tags"]].head(5).to_string(index=False))
