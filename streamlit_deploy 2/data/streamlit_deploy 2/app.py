"""
app.py — 営業情報検索App（画面）  担当：じんじん

構成
  ホーム         : 企業名検索（メイン）／キーワード検索（こだわり条件：地域・相談/決定・業種）
  取引先ページ    : 左＝対象企業（案件・接触履歴・企業情報をタブ切替）／右＝類似企業・キーワード検索
  結果ページ      : キーワード検索の結果。タグで絞り込み・並べ替え

使うモジュール
  database.py (がっきー) 8表の読み出し ／ ranking.py (ちか) 規模スコア ／ search.py (じんじん) 検索処理

起動：  streamlit run app.py   （data/app.db が無ければ CSV から自動で作る）

セキュリティ
  ・SQL はすべてプレースホルダ（database.py）。画面に出す文字列は html.escape で無害化する。
  ・.streamlit/secrets.toml（または Cloud の Secrets）に APP_PASSWORD があれば、入力しないと使えない。
    無ければパスワードなしで動く（ローカル確認用）。秘密情報はコードに書かない。
"""
import html
from datetime import date

import pandas as pd
import streamlit as st

import database as db
import search as sr

BRAND = "#0A3D91"
st.set_page_config(page_title="営業情報検索App", page_icon="🔎", layout="wide")


# ---- 起動時の準備 ---------------------------------------------------------------------------
def ensure_db():
    if not db.DB_PATH.exists() or db.DB_PATH.stat().st_size == 0:
        import import_data
        with st.spinner("データベースを準備しています…"):
            import_data.import_all_csv()


def check_password():
    """APP_PASSWORD が設定されているときだけ、パスワードを求める"""
    try:
        expected = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        expected = ""
    if not expected or st.session_state.get("authed"):
        return True
    st.markdown("### 営業情報検索App")
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン", type="primary"):
        if pw == expected:
            st.session_state.authed = True
            st.rerun()
        st.error("パスワードが違います")
    return False


# ---- 見た目（システムフォントで統一） ------------------------------------------------------------
st.markdown(f"""
<style>
  html, body, .stApp, .stApp *:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded) {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Yu Gothic UI", "Meiryo", "Hiragino Sans",
                 "Hiragino Kaku Gothic ProN", Roboto, "Noto Sans JP", sans-serif !important;
  }}
  .block-container {{ padding-top: 3.2rem; max-width: 1360px; }}
  .hd {{ display:flex; justify-content:space-between; align-items:baseline;
         border-bottom: 3px solid {BRAND}; padding: 4px 2px 8px; margin-bottom: 14px; }}
  .hd .t {{ font-size: 1.3rem; font-weight: 700; color: {BRAND}; }}
  .hd .s {{ font-size: .85rem; color: #666; }}
  .brief {{ border: 1px solid #dde3ec; border-left: 5px solid {BRAND}; border-radius: 6px;
            padding: 12px 16px; background: #fff; margin-bottom: 10px; line-height: 1.7; }}
  .k {{ color: #666; font-size: .82rem; }}
  .score {{ font-size: 1.5rem; font-weight: 700; color: {BRAND}; line-height: 1.1; }}
  .sub {{ color: #777; font-size: .78rem; }}
  .tag {{ display:inline-block; background:#EEF2F9; color:{BRAND}; border-radius: 4px;
          padding: 1px 8px; font-size: .75rem; margin: 2px 4px 2px 0; }}
  .tag.red {{ background:#FBEBEE; color:#B3121F; }}
  .foot {{ color:#999; font-size:.75rem; text-align:right; margin-top: 24px; }}
  div[data-testid="stMetric"] {{ background:#F4F6FA; border-radius: 6px; padding: 6px 12px; }}
</style>
""", unsafe_allow_html=True)


# ---- 表示用の小さな関数 ----------------------------------------------------------------------
def esc(v):
    """None/NaN は空、それ以外は HTML を無害化した文字列"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return html.escape(str(v))


def num(v):
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def fmt_man(v):
    v = num(v)
    if v is None:
        return "—"
    return f"{v/10000:,.1f}億円" if v >= 10000 else f"{v:,.0f}万円"


def fmt_yen(v):
    v = num(v)
    return "—" if v is None else fmt_man(v / 10000)


def fmt_int(v):
    v = num(v)
    return "—" if v is None else f"{v:,.0f}"


def jdate(s):
    try:
        d = date.fromisoformat(str(s)[:10])
        return f"{d.year}/{d.month}/{d.day}"
    except Exception:
        return "—"


def days_ago(s):
    try:
        return (date.today() - date.fromisoformat(str(s)[:10])).days
    except Exception:
        return None


def tag_html(tags):
    return "".join(f'<span class="tag{" red" if t in ("謝絶", "取下") else ""}">{esc(t)}</span>' for t in tags)


# ---- 画面遷移 ------------------------------------------------------------------------------
if "page" not in st.session_state:
    st.session_state.update(page="home", customer_id=None, kw_query="", kw_filters={}, history=[])


def go(page, **kw):
    st.session_state.history.append((st.session_state.page, st.session_state.customer_id))
    st.session_state.page = page
    for k, v in kw.items():
        st.session_state[k] = v
    st.rerun()


def go_back():
    if st.session_state.history:
        st.session_state.page, st.session_state.customer_id = st.session_state.history.pop()
    else:
        st.session_state.page = "home"
    st.rerun()


@st.cache_data(show_spinner=False, ttl=3600)
def cached_similar(customer_id):
    return sr.similar_companies(customer_id)


@st.cache_data(show_spinner=False, ttl=3600)
def cached_keyword(keyword, base_id, industry, city_code, record_type, one):
    return sr.search_keyword(keyword, base_customer_id=base_id, industry=industry, city_code=city_code,
                             record_type=record_type, one_per_company=one)


def header(sub=""):
    t = date.today()
    st.markdown(f'<div class="hd"><span class="t">営業情報検索App</span>'
                f'<span class="s">{esc(sub)}{"　｜　" if sub else ""}{t.year}/{t.month}/{t.day}</span></div>',
                unsafe_allow_html=True)


def footer():
    st.markdown('<div class="foot">テクゼロンBANK 法人営業　開発：ちか・がっきー・じんじん</div>', unsafe_allow_html=True)


# ============================================================================================
# ホーム
# ============================================================================================
def page_home():
    header()
    st.markdown("#### 企業名検索")
    name = st.text_input("企業名（一部でも可）", placeholder="例：こむぎ堂、ひまわり、ベーカリー",
                         max_chars=50, label_visibility="collapsed")
    if name.strip():
        hits = db.search_customers(name, limit=30)
        if not hits:
            st.info("該当する取引先がありません。")
        else:
            st.caption(f"{len(hits)} 件")
            for h in hits:
                c = st.columns([4, 2, 2, 2, 1.2])
                c[0].markdown(f"**{esc(h['name'])}**")
                c[1].markdown(f"<span class='k'>{esc(h['industry'])}</span>", unsafe_allow_html=True)
                c[2].markdown(f"<span class='k'>{esc(h['city_display_name'])}</span>", unsafe_allow_html=True)
                c[3].markdown(f"<span class='k'>{esc(h['branch_name'])}</span>", unsafe_allow_html=True)
                if c[4].button("開く", key=f"open_{h['id']}", use_container_width=True):
                    go("customer", customer_id=h["id"])

    st.divider()
    st.markdown("#### キーワード検索")
    q = st.text_input("キーワード", placeholder="例：事業承継　設備資金　借換（空白区切りで AND）",
                      max_chars=sr.MAX_QUERY_LEN, label_visibility="collapsed")
    g1, g2, g3, g4 = st.columns([2, 1.5, 2, 1.5])
    cities = db.list_cities()
    city_map = {c["display_name"]: c["city_code"] for c in cities}
    city_sel = g1.selectbox("地域（市区町村）", ["指定なし"] + list(city_map))
    rtype = g2.selectbox("記録の種類", ["相談＋決定", "相談", "決定"])
    ind_sel = g3.selectbox("業種", ["指定なし"] + db.list_industries())
    one = g4.checkbox("1社1記録にまとめる", value=True)
    if st.button("検索", type="primary") and q.strip():
        go("results", kw_query=sr.clean_query(q), kw_filters=dict(
            city_code=city_map.get(city_sel), city_name=None if city_sel == "指定なし" else city_sel,
            industry=None if ind_sel == "指定なし" else ind_sel,
            record_type=None if rtype == "相談＋決定" else rtype, one=one))
    footer()


# ============================================================================================
# 取引先ページ
# ============================================================================================
def page_customer():
    cid = st.session_state.customer_id
    cu = db.get_customer(cid)
    if cu is None:
        st.error("取引先が見つかりません")
        if st.button("← 戻る"):
            go_back()
        return
    header(cu["name"])
    b1, b2 = st.columns([1, 9])
    if b1.button("← 戻る"):
        go_back()
    b2.caption(f"{cu['branch_name']}　主担当：{cu['staff_name'] or '—'}　｜　{cu['industry']}　｜　{cu['city_display_name'] or ''}")

    left, right = st.columns([1, 1.15], gap="large")

    # ---- 左：対象企業 ----
    with left:
        logs, deals = db.get_contact_logs(cid), db.get_deals(cid)
        last = logs[0] if logs else None
        n_done = sum(1 for d in deals if d["status"] == "実行済")
        n_wip = sum(1 for d in deals if d["status"] == "処理中")
        n_ng = sum(1 for d in deals if d["status"] in ("謝絶", "取下"))
        if last:
            ago = days_ago(last["contact_date"])
            last_line = (f"{jdate(last['contact_date'])}（{ago}日前・{esc(last['staff_name'])}・{esc(last['purpose'])}）"
                         if ago is not None else jdate(last["contact_date"]))
            nxt = esc(last["next_action"]) or "—"
            if last.get("next_date"):
                nxt += f"（予定 {jdate(last['next_date'])}）"
            content = esc((last["content"] or "")[:70])
        else:
            last_line, nxt, content = "—", "—", "—"
        st.markdown(f"""<div class="brief"><b>直近の状況</b><br>
<span class="k">最終接触</span>　{last_line}<br>
<span class="k">内容</span>　{content}<br>
<span class="k">次回</span>　{nxt}<br>
<span class="k">案件</span>　{len(deals)} 件（実行済 {n_done}・処理中 {n_wip}・謝絶/取下 {n_ng}）</div>""",
                    unsafe_allow_html=True)

        t1, t2, t3 = st.tabs([f"案件（{len(deals)}）", f"接触履歴（{len(logs)}）", "企業情報"])
        with t1:
            if not deals:
                st.caption("案件はありません")
            for d in deals:
                with st.container(border=True):
                    a, b = st.columns([3, 1])
                    a.markdown(f"**{esc(d['deal_name'])}**　<span class='k'>{esc(d['deal_type'])}・受付 {jdate(d['received_date'])}・{esc(d['staff_name'])}</span>",
                               unsafe_allow_html=True)
                    b.markdown(tag_html([d["status"] or ""]), unsafe_allow_html=True)
                    line = (f"<span class='k'>申込金額</span> {fmt_yen(d['amount_yen'])}　"
                            f"<span class='k'>経緯</span> {esc(d['background'])}　<span class='k'>状況</span> {esc(d['situation'])}")
                    if d.get("decline_reason"):
                        line += f"　<span class='k'>謝絶理由</span> {esc(d['decline_reason'])}"
                    st.markdown(line, unsafe_allow_html=True)
        with t2:
            if not logs:
                st.caption("接触履歴はありません")
            for l in logs[:30]:
                with st.container(border=True):
                    st.markdown(f"**{jdate(l['contact_date'])}　{esc(l['purpose'])}**　<span class='k'>{esc(l['method'])}・{esc(l['partner'])}・{esc(l['staff_name'])}</span>",
                                unsafe_allow_html=True)
                    st.markdown(f"{esc(l['content'])}<br><span class='k'>反応</span> {esc(l['reaction']) or '—'}　"
                                f"<span class='k'>次回</span> {esc(l['next_action']) or '—'}", unsafe_allow_html=True)
            if len(logs) > 30:
                st.caption(f"ほか {len(logs) - 30} 件")
        with t3:
            m1, m2, m3 = st.columns(3)
            m1.metric("売上高（最新期）", fmt_man(cu["sales_man_yen"]))
            m2.metric("従業員数", fmt_int(cu["employees"]) + " 人")
            m3.metric("資本金", fmt_yen(cu["capital_yen"]))
            info = pd.DataFrame({
                "項目": ["会社名", "業種", "設立", "所在地", "決算期", "経常利益", "評点", "法人番号 / TDB", "当行取引"],
                "内容": [cu["company_name"], cu["industry"], f"{cu['established'] or '—'} 年", cu["address"] or "—",
                        f"{cu['latest_fiscal_year'] or '—'} 年", fmt_man(cu["profit_man_yen"]), str(cu["score"] or "—"),
                        f"{cu['corporate_number'] or '—'} / {cu['tdb_code'] or '—'}",
                        f"{cu['branch_name']}（{cu['block_name'] or ''}）　店内番号 {cu['branch_customer_no'] or '—'}"],
            })
            st.dataframe(info, hide_index=True, use_container_width=True)

    # ---- 右：類似企業／キーワード検索 ----
    with right:
        r1, r2 = st.tabs(["類似企業", "キーワード検索"])
        with r1:
            sim = cached_similar(cid)
            if sim.empty:
                st.caption("同業種の取引先がありません")
            else:
                c1, c2 = st.columns([3, 1.4])
                c1.markdown(f"同業種「{esc(cu['industry'])}」{len(sim)} 社　<span class='k'>売上高 50・従業員数 30・資本金 20 の 100 点</span>",
                            unsafe_allow_html=True)
                topn = c2.selectbox("表示件数", [10, 20, 50, len(sim)], label_visibility="collapsed",
                                    format_func=lambda n: f"{n} 社" if n != len(sim) else "すべて")
                for _, r in sim.head(topn).iterrows():
                    render_similar_row(cu, r)
        with r2:
            q = st.text_input("キーワード", placeholder="例：事業承継　設備資金　借換", max_chars=sr.MAX_QUERY_LEN,
                              key="cust_kw", label_visibility="collapsed")
            st.caption("同業種の記録から探し、規模スコア 70%＋文章の近さ 30% で並べます")
            if q.strip():
                render_results(cached_keyword(sr.clean_query(q), cid, None, None, None, True), key_prefix="cust")
    footer()


def render_similar_row(base, r):
    with st.container(border=True):
        a, b, c = st.columns([3.4, 1, 0.9])
        a.markdown(f"**{int(r['rank'])}. {esc(r['customer_name'])}**<br><span class='k'>{esc(r['branch_name'])}・{esc(r['city_display_name'])}</span>",
                   unsafe_allow_html=True)
        b.markdown(f"<div class='score'>{r['total_score']:.0f}<span style='font-size:.8rem'> 点</span></div>", unsafe_allow_html=True)
        if c.button("開く", key=f"sim_{r['customer_id']}", use_container_width=True):
            go("customer", customer_id=int(r["customer_id"]))
        st.markdown(f"<span class='k'>売上</span> {fmt_man(r['sales_man_yen'])}　<span class='k'>従業員</span> {fmt_int(r['employees'])} 人　"
                    f"<span class='k'>資本金</span> {fmt_yen(r['capital_yen'])}　"
                    f"<span class='sub'>内訳 {r['sales_score']:.0f}／{r['employees_score']:.0f}／{r['capital_score']:.0f}</span>",
                    unsafe_allow_html=True)
        last = db.get_latest_contact(int(r["customer_id"]))
        if last:
            st.markdown(f"<span class='k'>直近</span> {jdate(last['contact_date'])} {esc(last['purpose'])}（{esc(last['staff_name'])}）"
                        f"— {esc((last['content'] or '')[:50])}", unsafe_allow_html=True)


# ============================================================================================
# キーワード検索の結果（タグで絞り込み・並べ替え）
# ============================================================================================
def render_results(df, key_prefix="res"):
    if df is None or df.empty:
        st.info("該当する記録がありません。")
        return
    tags = sr.all_tags(df)
    tag_count = dict(tags)
    c1, c2, c3 = st.columns([3, 1.3, 1.3])
    sel = c1.multiselect("タグで絞り込む", [t for t, _ in tags], format_func=lambda t: f"{t}（{tag_count[t]}）",
                         key=f"{key_prefix}_tags")
    mode = c2.radio("条件", ["すべて含む", "どれか含む"], horizontal=True, key=f"{key_prefix}_mode")
    has_size = not df["size_score"].isna().all()
    keys = [k for k in sr.SORT_KEYS if has_size or k != "規模の近い順"]
    sort_key = c3.selectbox("並べ替え", keys, key=f"{key_prefix}_sort")
    df = sr.sort_results(sr.filter_by_tags(df, sel, "all" if mode == "すべて含む" else "any"), sort_key)
    st.caption(f"{len(df)} 件")
    for _, r in df.head(40).iterrows():
        with st.container(border=True):
            a, b, c = st.columns([3.6, 1.1, 0.8])
            a.markdown(f"**{int(r['rank'])}. {esc(r['customer_name'])}**　<span class='k'>{esc(r['record_type'])}・{jdate(r['record_date'])}・{esc(r['staff_name'])}</span><br>"
                       f"{tag_html(r['tags'])}", unsafe_allow_html=True)
            if has_size:
                b.markdown(f"<div class='score'>{r['total']:.0f}<span style='font-size:.8rem'> 点</span></div>"
                           f"<span class='sub'>規模 {r['size_score']:.0f}・文章 {r['relevance']*100:.0f}</span>", unsafe_allow_html=True)
            else:
                b.markdown(f"<div class='score'>{r['relevance']*100:.0f}<span style='font-size:.8rem'> %</span></div>"
                           f"<span class='sub'>文章の近さ</span>", unsafe_allow_html=True)
            if c.button("開く", key=f"{key_prefix}_open_{r['record_key']}", use_container_width=True):
                go("customer", customer_id=int(r["customer_id"]))
            title = r["deal_name"] if r["record_type"] == "決定" else r["purpose"]
            body = f"**{esc(title)}**"
            if r["record_type"] == "決定":
                body += f"　<span class='k'>金額</span> {fmt_yen(r['amount_yen'])}"
                if esc(r.get("status")):
                    body += f"　{tag_html([r['status']])}"
            body += f"<br>{esc((r['content'] or '')[:120])}"
            if esc(r.get("reaction")):
                body += f"<br><span class='k'>反応</span> {esc(r['reaction'])}"
            if esc(r.get("decline_reason")):
                body += f"<br><span class='k'>謝絶理由</span> {esc(r['decline_reason'])}"
            st.markdown(body, unsafe_allow_html=True)
            st.markdown(f"<span class='k'>{esc(r['industry'])}・{esc(r['city_display_name'])}・売上 {fmt_man(r['sales_man_yen'])}・従業員 {fmt_int(r['employees'])} 人</span>",
                        unsafe_allow_html=True)
    if len(df) > 40:
        st.caption(f"ほか {len(df) - 40} 件。タグで絞り込んでください。")


def page_results():
    header("キーワード検索")
    b1, b2 = st.columns([1, 9])
    if b1.button("← 戻る"):
        go_back()
    f, q = st.session_state.kw_filters, st.session_state.kw_query
    cond = "／".join(x for x in [f.get("industry"), f.get("city_name"), f.get("record_type")] if x) or "条件なし"
    b2.markdown(f"**{esc(q)}**　<span class='k'>{esc(cond)}</span>", unsafe_allow_html=True)
    with st.spinner("検索中…"):
        df = cached_keyword(q, None, f.get("industry"), f.get("city_code"), f.get("record_type"), f.get("one", True))
    render_results(df, key_prefix="res")
    footer()


# ============================================================================================
if check_password():
    ensure_db()
    {"home": page_home, "customer": page_customer, "results": page_results}[st.session_state.page]()
