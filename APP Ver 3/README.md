# 営業情報検索App（最終版）

テクゼロンBANK 法人営業向け。過去の接触履歴・案件（行員の行動履歴＝知見）を検索し、
**同業種で規模の近い会社の過去事例** と **キーワード（事業承継・設備資金 など）に合う事例** をすぐ引けるようにする。

開発：ちか（ランキング）・がっきー（DB・データ）・じんじん（画面・検索処理）

## 1. 動かし方（ローカル）

```bash
cd app2
python -m venv .venv
.venv\Scripts\activate          # Windows（Mac: source .venv/bin/activate）
pip install -r requirements.txt
python import_data.py           # CSV → data/app.db
streamlit run app.py
```

- `data/app.db` が無くても、起動時に CSV から自動で作ります。
- 比較用の 5 社（パン工場・大手メーカーの宮崎工場）を CSV に足すときは、先に `python add_demo_companies.py`（何度実行しても二重には入らない）。

## 2. 画面

| 画面 | 内容 |
|---|---|
| ホーム | **企業名検索**（メイン）／**キーワード検索**（こだわり条件：地域・相談/決定・業種、1社1記録） |
| 取引先ページ | 左＝直近の状況＋**案件／接触履歴／企業情報**（タブ切替）。右＝**類似企業**／**キーワード検索**（タブ切替） |
| 結果ページ | キーワード検索の結果。**タグで絞り込み・並べ替え**（相談・決定・実行済・謝絶・事業承継・設備資金・補助金…） |

## 3. 類似企業のスコア（ranking.py）

- 業種は **マスト条件**（同業種の取引先だけを候補にする）。
- 配点：**売上高 50・従業員数 30・資本金 20**（100 点満点）。
- 基準の会社との差率で段階評価：±20% 以内＝満点、±50% 以内＝7 割、±100% 以内＝4 割、それ以上＝0 点。欠損は 0 点。
- 画面側は `ranking.rank_companies(company_id, candidate_ids=同業種の取引先, same_industry=True)` を呼ぶだけで、ranking.py 自体は変更していない。

キーワード検索は、記録（相談・決定）を文章の近さ（文字 2〜3-gram の TF-IDF）で探し、
取引先ページから使うときは **規模スコア 70%＋文章の近さ 30%** で並べる（search.py）。
タグは記録の種類・目的・状況・本文のキーワードから自動で付ける（入力は増やさない。辞書は `search.py` の `NEED_TAGS`）。

## 4. ファイル

| ファイル | 役割 | 担当 |
|---|---|---|
| schema.sql / database.py / import_data.py | 8 表の定義・読み出し・CSV 取り込み（`database.py` 末尾の 2 関数は画面用の追記） | がっきー |
| ranking.py | 規模スコア（50/30/20） | ちか |
| search.py | 類似企業・キーワード検索・タグ（ranking.py と database.py をつなぐ） | じんじん |
| app.py | 画面 | じんじん |
| add_demo_companies.py | 比較用の 5 社＋接触履歴 9 件＋案件 5 件を CSV に追加 | じんじん |
| .streamlit/config.toml | 配色（紺 #0A3D91）。フォントはシステムフォントで統一（app.py の CSS） | じんじん |

## 5. セキュリティ・デプロイ

**コードの中**
- SQL はすべてプレースホルダ（SQL インジェクション対策）。画面に出す文字列は `html.escape` で無害化。
- 検索語は 50 文字まで。外部 API・外部サーバーへの通信はしない。
- `APP_PASSWORD` を設定すると、パスワードを入れないと使えない（未設定ならパスワードなしで動く）。
  設定方法：`.streamlit/secrets.toml.example` を `secrets.toml` にコピーして値を入れる。

**Git・公開時（W5 の学び）**
1. `.env`・`.streamlit/secrets.toml`・`data/app.db` は `.gitignore` で除外済み。秘密情報はコードに書かない。
2. Streamlit Community Cloud に載せるときは、App settings → **Secrets** に `APP_PASSWORD = "…"` を登録する。
3. リポジトリは **Private** にする。本物の顧客データは公開環境に置かない（今のデータはすべて架空）。
4. `requirements.txt` を置く。push すると自動で再ビルドされる。Python は 3.11 を指定する。
5. 本番は行内サーバー／閉域で動かし、閲覧範囲（支店・担当）の制御を要件に加える。
