import pandas as pd
import FinanceDataReader as fdr
import os
import argparse
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# 실행 인자 설정
# 사용법: python inspector.py --cap 5천억 --price close
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser(description="수급 강도 전략 - 월별 종목 상세 검증")
parser.add_argument("--cap", type=str, default="5천억", choices=["2천억", "5천억"],
                    help="분석할 시총 폴더 선택 (2천억 또는 5천억)")
parser.add_argument("--price", type=str, default="close",
                    choices=["open", "close", "vwap"],
                    help="수익률 계산 기준 (open: 시가, close: 종가, vwap: 거래량가중평균)")
args = parser.parse_args()

PRICE_LABEL = {"open": "시가(Open)", "close": "종가(Close)", "vwap": "VWAP"}

# 설정
BASE_DIR = os.path.join(os.path.dirname(__file__), f"../../data/file/monthly_csv_data/시총{args.cap}")
INVEST_YEAR = 2025


def _get_entry_exit_price(df_price, method):
    """주어진 OHLCV 데이터에서 매수가/매도가를 반환"""
    if method == "open":
        entry = df_price['Open'].iloc[0]
        exit_ = df_price['Open'].iloc[-1]
    elif method == "close":
        entry = df_price['Close'].iloc[0]
        exit_ = df_price['Close'].iloc[-1]
    elif method == "vwap":
        typical = (df_price['High'] + df_price['Low'] + df_price['Close']) / 3
        entry = typical.iloc[0]
        exit_ = typical.iloc[-1]
    else:
        raise ValueError(f"지원하지 않는 가격 기준: {method}")
    return entry, exit_


def get_stock_detail_returns(ticker, start, end, method="close"):
    """특정 기간의 수익률을 지정된 가격 기준으로 계산"""
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


def inspect_monthly_details(price_method="close"):
    files = sorted([f for f in os.listdir(BASE_DIR) if f.endswith('.csv')])

    for file_name in files:
        # 파일명에서 선정 월 추출
        month_str = file_name.split('_')[1].replace('월', '')
        select_month = int(month_str)
        print(f"== 파일 처리 중: {file_name} ==")

        # 투자 기간 설정 (N월 선정 -> N+1월 투자)
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

        print(f"\n{'=' * 65}")
        print(f"  {year}년 {invest_month:02d}월 투자 종목 성적표 "
              f"(선정: {select_month}월 | 기준: {PRICE_LABEL[price_method]})")
        print(f"{'=' * 65}")

        df = pd.read_csv(os.path.join(BASE_DIR, file_name))
        df['티커'] = df['티커'].astype(str).str.zfill(6)

        # 가중치 계산
        df['score'] = df['비고'].apply(lambda x: 2 if '중복' in str(x) else 1)
        df['weight'] = df['score'] / df['score'].sum()

        monthly_total_ret = 0

        # 각 종목별 수익률 출력
        for _, row in df.iterrows():
            ret = get_stock_detail_returns(row['티커'], start_date, end_date, method=price_method)
            contribution = ret * row['weight']
            monthly_total_ret += contribution

            mark = "**" if '중복' in str(row['비고']) else "  "
            print(f"  {mark} {row['종목명']:12s} | "
                  f"수익률: {ret * 100:7.2f}% | "
                  f"비중: {row['weight'] * 100:5.1f}% | "
                  f"기여도: {contribution * 100:7.3f}% | "
                  f"{row['비고']}")

        print(f"  {'-' * 61}")
        print(f"  >>> {invest_month}월 포트폴리오 합계 수익률: {monthly_total_ret * 100:.2f}%")


if __name__ == "__main__":
    inspect_monthly_details(price_method=args.price)
