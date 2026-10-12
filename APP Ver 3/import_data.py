"""
import_data.py — CSVをDBに読み込む（作る側が手動で実行する。担当：がっきー）

使い方：  python import_data.py

・data/ にある8本のCSVを、表のつながりの順に読み込む
・毎回いったん中身を空にしてから入れ直す（CSVを直したら、もう一度実行すればよい）
・途中で1つでも失敗したら、全部を元に戻す（中途半端なDBを残さない）
・CSVは最初から番号（取引先ID・担当者ID）を持っているので、名前→番号の置き換えはしない
"""

import csv
import sys
from pathlib import Path

from database import get_connection, init_db, BASE_DIR

DATA_DIR = BASE_DIR / "data"

# 読み込む順番＝参照される表が先（CSVファイル名とテーブル名は同じ）
TABLES = [
    "master_city",
    "master_company",
    "company_financials",
    "master_gbizinfo",
    "staff",
    "customers",
    "contact_logs",
    "deals",
]


def import_all_csv():
    init_db()

    missing = [t for t in TABLES if not (DATA_DIR / f"{t}.csv").exists()]
    if missing:
        print("[中止] 次のCSVが data/ にありません：", ", ".join(missing))
        sys.exit(1)

    conn = get_connection()
    conn.execute("PRAGMA foreign_keys = OFF")  # 入れ替え中だけ外す。最後にまとめて確認する
    try:
        with conn:  # ここを抜けるとき、成功ならまとめて保存、失敗なら全部元に戻る
            for table in reversed(TABLES):
                conn.execute(f"DELETE FROM {table}")

            for table in TABLES:
                table_cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})")]
                with (DATA_DIR / f"{table}.csv").open(encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    extra = [c for c in reader.fieldnames if c not in table_cols]
                    if extra:
                        print(f"  - [注意] {table}: 表にない列を無視します → {extra}")
                    cols = [c for c in reader.fieldnames if c in table_cols]
                    sql = (f"INSERT INTO {table} ({', '.join(cols)}) "
                           f"VALUES ({', '.join('?' * len(cols))})")
                    rows = [[(r[c] if r[c] != "" else None) for c in cols] for r in reader]
                    conn.executemany(sql, rows)
                print(f"  - [成功] {table}: {len(rows):,} 件")

            broken = conn.execute("PRAGMA foreign_key_check").fetchall()
            if broken:
                print(f"[中止] つながりの切れた行が {len(broken)} 件あります（例：{tuple(broken[0])}）")
                raise RuntimeError("foreign key check failed")
    except Exception as e:
        print(f"[失敗] 取り込みを元に戻しました：{e}")
        sys.exit(1)
    finally:
        conn.close()

    print("すべての取り込みが終わりました（data/app.db）")


if __name__ == "__main__":
    import_all_csv()
