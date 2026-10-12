営業情報検索App - Streamlit Community Cloud用

構成:
  app.py
  database.py
  ranking.py
  search.py
  schema.sql
  requirements.txt
  data/app.db

ローカル起動:
  pip install -r requirements.txt
  streamlit run app.py

Streamlit Community Cloud:
  このフォルダの中身をGitHubリポジトリのルートに配置し、Main file pathに app.py を指定してください。
  app.db は data/app.db に置いたままにしてください。
