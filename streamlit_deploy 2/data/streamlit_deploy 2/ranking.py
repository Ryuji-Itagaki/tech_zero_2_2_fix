"""テクゼロ銀行：企業規模の類似度ランキング（MVP）

配点：売上高50点、従業員数30点、資本金20点。
使い方（プロジェクト直下で実行）: python ranking.py 1
CSVは data/ に置く。基準企業IDは引数で指定する。
業種・地域・キーワードの検索は画面側/検索処理側で行い、
その検索結果の company_id を candidate_ids に渡す。
"""
import argparse
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
WEIGHTS = {'sales_man_yen': 50, 'employees': 30, 'capital_yen': 20}


def read_csv(filename, data_dir=DATA_DIR):
    with (Path(data_dir) / filename).open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


def to_number(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        result = float(value)
        return result if result >= 0 else None
    except (ValueError, TypeError):
        return None


def load_companies(data_dir=DATA_DIR):
    """企業マスタ＋最新年度の財務数値＋資本金を企業IDで結合する。"""
    companies = {}
    for row in read_csv('master_company.csv', data_dir):
        companies[int(row['company_id'])] = {
            'company_id': int(row['company_id']),
            'company_name': row['company_name'],
            'industry': row['industry'],
            'address': row['address'],
            'city_code': row['city_code'],
            'corporate_number': row['corporate_number'],
            'sales_man_yen': None, 'employees': None, 'capital_yen': None,
            'fiscal_year': None,
        }
    for row in read_csv('company_financials.csv', data_dir):
        company = companies.get(int(row['company_id']))
        if company is None:
            continue
        year = int(row['fiscal_year'])
        if company['fiscal_year'] is None or year > company['fiscal_year']:
            company['fiscal_year'] = year
            company['sales_man_yen'] = to_number(row['sales_man_yen'])
            company['employees'] = to_number(row['employees'])
    capital_by_number = {
        row['corporate_number']: to_number(row['capital_yen'])
        for row in read_csv('master_gbizinfo.csv', data_dir)
    }
    for company in companies.values():
        company['capital_yen'] = capital_by_number.get(company['corporate_number'])
    return companies


def similarity_score(base, other, max_points):
    """基準値に対する差率で段階評価。欠損値は0点（未評価）。"""
    if base is None or other is None:
        return 0.0
    if base == 0:
        return float(max_points) if other == 0 else 0.0
    difference = abs(other - base) / base
    if difference <= 0.20:
        ratio = 1.0
    elif difference <= 0.50:
        ratio = 0.7
    elif difference <= 1.00:
        ratio = 0.4
    else:
        ratio = 0.0
    return round(max_points * ratio, 2)


def score_company(base, other):
    scores = {
        'sales_score': similarity_score(base['sales_man_yen'], other['sales_man_yen'], 50),
        'employees_score': similarity_score(base['employees'], other['employees'], 30),
        'capital_score': similarity_score(base['capital_yen'], other['capital_yen'], 20),
    }
    scores['total_score'] = round(sum(scores.values()), 2)
    scores['missing_fields'] = [
        field for field in WEIGHTS
        if base.get(field) is None or other.get(field) is None
    ]
    return scores


def rank_companies(base_company_id, candidate_ids=None, data_dir=DATA_DIR, same_industry=False):
    """検索結果の候補企業を順位付け。候補未指定なら全企業を比較。"""
    companies = load_companies(data_dir)
    base_company_id = int(base_company_id)
    if base_company_id not in companies:
        raise ValueError(f'基準企業ID {base_company_id} が見つかりません')
    base = companies[base_company_id]
    allowed = None if candidate_ids is None else {int(cid) for cid in candidate_ids}
    results = []
    for company_id, company in companies.items():
        if company_id == base_company_id:
            continue
        if allowed is not None and company_id not in allowed:
            continue
        if same_industry and company['industry'] != base['industry']:
            continue
        results.append({**company, **score_company(base, company)})
    results.sort(key=lambda row: (-row['total_score'], row['company_name'], row['company_id']))
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='企業規模の類似度ランキング')
    parser.add_argument('company_id', type=int, help='基準企業ID')
    parser.add_argument('--same-industry', action='store_true', help='同業種に限定')
    parser.add_argument('--limit', type=int, default=10, help='表示件数')
    args = parser.parse_args()
    ranked = rank_companies(args.company_id, same_industry=args.same_industry)
    print('順位 | 企業ID | 企業名 | 売上高 | 従業員数 | 資本金 | 合計')
    for position, company in enumerate(ranked[:args.limit], 1):
        print(f"{position} | {company['company_id']} | {company['company_name']} | "
              f"{company['sales_score']:.0f} | {company['employees_score']:.0f} | "
              f"{company['capital_score']:.0f} | {company['total_score']:.0f}")
