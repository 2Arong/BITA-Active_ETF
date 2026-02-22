import pandas as pd
import FinanceDataReader as fdr
import os
import argparse
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# 실행 인자 설정
# 사용법: python inspector_score_weighted.py --cap 5천억 --price close
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="수급 강도 전략 - 월별 종목 상세 검증 (동일비중 vs 점수비중)")
parser.add_argument("--cap", type=str, default="5천억", choices=["2천억", "5천억"],
                    help="분석할 시총 폴더 선택")
parser.add_argument("--price", type=str, default="close",
                    choices=["open", "close", "vwap"],
                    help="수익률 계산 기준 (open/close/vwap)")
args = parser.parse_args()

PRICE_LABEL = {"open": "시가(Open)", "close": "종가(Close)", "vwap": "VWAP"}

BASE_DIR = os.path.join(os.path.dirname(__file__), f"../../data/file/monthly_csv_data/시총{args.cap}")
INVEST_YEAR = 2025


# ─────────────────────────────────────────────
# 가격 및 수익률 계산
# ─────────────────────────────────────────────
def _get_entry_exit_price(df_price, method):
    if method == "open":
        return df_price['Open'].iloc[0], df_price['Open'].iloc[-1]
    elif method == "close":
        return df_price['Close'].iloc[0], df_price['Close'].iloc[-1]
    elif method == "vwap":
        typical = (df_price['High'] + df_price['Low'] + df_price['Close']) / 3
        return typical.iloc[0], typical.iloc[-1]
    raise ValueError(f"지원하지 않는 가격 기준: {method}")


def get_stock_detail_returns(ticker, start, end, method="close"):
    try:
        df = fdr.DataReader(ticker, start, end)
        if df.empty or len(df) < 2:
            print(f"    [경고] {ticker}: 데이터 부족")
            return 0
        entry, exit_ = _get_entry_exit_price(df, method)
        if entry == 0:
            print(f"    [경고] {ticker}: 매수가가 0")
            return 0
        return (exit_ / entry) - 1
    except Exception as e:
        print(f"    [에러] {ticker}: {e}")
        return 0


# ─────────────────────────────────────────────
# 비중 계산
# ─────────────────────────────────────────────
def calc_equal_weight(df):
    scores = df['비고'].apply(lambda x: 2 if '중복' in str(x) else 1)
    return scores / scores.sum()


def calc_score_weight(df):
    scores = df['최종점수'].clip(lower=0)
    total = scores.sum()
    if total == 0:
        return pd.Series(1 / len(df), index=df.index)
    return scores / total


# ─────────────────────────────────────────────
# 월별 상세 검증 (두 비중 방식 비교)
# ─────────────────────────────────────────────
def inspect_monthly_details(price_method="close"):
    files = sorted([f for f in os.listdir(BASE_DIR) if f.endswith('.csv')])

    for file_name in files:
        month_str = file_name.split('_')[1].replace('월', '')
        select_month = int(month_str)

        invest_month = select_month + 1
        year = INVEST_YEAR
        if invest_month > 12:
            invest_month = 1
            year += 1

        start_date = f"{year}-{invest_month:02d}-01"
        if invest_month == 12:
            end_date = f"{year}-12-31"
        else:
            end_date = (datetime(year, invest_month + 1, 1) - timedelta(days=1)).strftime('%Y-%m-%d')

        print(f"\n{'=' * 95}")
        print(f"  {year}년 {invest_month:02d}월 투자 종목 성적표 "
              f"(선정: {select_month}월 | {PRICE_LABEL[price_method]})")
        print(f"{'=' * 95}")

        df = pd.read_csv(os.path.join(BASE_DIR, file_name))
        df['티커'] = df['티커'].astype(str).str.zfill(6)

        w_equal = calc_equal_weight(df)
        w_score = calc_score_weight(df)

        total_ew = 0
        total_sw = 0

        header = (f"  {'':2s} {'종목명':12s} | {'수익률':>8s} | "
                  f"{'동일비중':>8s} {'기여도':>8s} | "
                  f"{'점수비중':>8s} {'기여도':>8s} | {'비고'}")
        print(header)
        print(f"  {'-' * 89}")

        for i, (_, row) in enumerate(df.iterrows()):
            ret = get_stock_detail_returns(row['티커'], start_date, end_date, method=price_method)

            contrib_ew = ret * w_equal.iloc[i]
            contrib_sw = ret * w_score.iloc[i]
            total_ew += contrib_ew
            total_sw += contrib_sw

            mark = "**" if '중복' in str(row['비고']) else "  "
            print(f"  {mark} {row['종목명']:12s} | "
                  f"{ret * 100:+7.2f}% | "
                  f"{w_equal.iloc[i] * 100:6.1f}% {contrib_ew * 100:+7.3f}% | "
                  f"{w_score.iloc[i] * 100:6.1f}% {contrib_sw * 100:+7.3f}% | "
                  f"{row['비고']}")

        print(f"  {'-' * 89}")
        print(f"  >>> 동일비중 합계: {total_ew * 100:+.2f}%  |  점수비중 합계: {total_sw * 100:+.2f}%  |  "
              f"차이: {(total_sw - total_ew) * 100:+.2f}%p")


if __name__ == "__main__":
    inspect_monthly_details(price_method=args.price)
