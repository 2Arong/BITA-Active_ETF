import pandas as pd
import FinanceDataReader as fdr
import os
import argparse
from collections import OrderedDict

# ─────────────────────────────────────────────
# 실행 인자
# 사용법: python inspector_2w.py --signal 외국인단독 --price close
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="2주 리밸런싱 - 그룹별 종목 상세 검증 (동일비중 vs 점수비중)")
parser.add_argument("--signal", type=str, default="외국인단독",
                    choices=["외국인단독", "기관포함"],
                    help="시그널 유형 선택")
parser.add_argument("--price", type=str, default="close",
                    choices=["open", "close", "vwap"],
                    help="수익률 계산 기준")
args = parser.parse_args()

PRICE_LABEL = {"open": "시가(Open)", "close": "종가(Close)", "vwap": "VWAP"}

BASE_DIR = os.path.join(os.path.dirname(__file__), f"../../data/file/rebal_2w_csv/{args.signal}")

# ─────────────────────────────────────────────
# 그룹별 투자 기간
# ─────────────────────────────────────────────
GROUP_PERIODS = OrderedDict({
    "g1":  ("2025-01-02", "2025-01-15"),
    "g2":  ("2025-01-16", "2025-02-04"),
    "g3":  ("2025-02-05", "2025-02-18"),
    "g4":  ("2025-02-19", "2025-03-06"),
    "g5":  ("2025-03-07", "2025-03-20"),
    "g6":  ("2025-03-21", "2025-04-03"),
    "g7":  ("2025-04-04", "2025-04-17"),
    "g8":  ("2025-04-18", "2025-05-02"),
    "g9":  ("2025-05-07", "2025-05-20"),
    "g10": ("2025-05-21", "2025-06-02"),
    "g11": ("2025-06-04", "2025-06-18"),
    "g12": ("2025-06-19", "2025-07-02"),
    "g13": ("2025-07-03", "2025-07-16"),
    "g14": ("2025-07-17", "2025-07-30"),
    "g15": ("2025-07-31", "2025-08-13"),
    "g16": ("2025-08-14", "2025-08-29"),
    "g17": ("2025-09-01", "2025-09-12"),
    "g18": ("2025-09-15", "2025-09-26"),
    "g19": ("2025-09-29", "2025-10-17"),
    "g20": ("2025-10-20", "2025-10-31"),
    "g21": ("2025-11-03", "2025-11-14"),
    "g22": ("2025-11-17", "2025-11-28"),
    "g23": ("2025-12-01", "2025-12-12"),
    "g24": ("2025-12-15", "2025-12-29"),
    "g25": ("2025-12-30", "2026-01-14"),
})

GROUP_KEYS = list(GROUP_PERIODS.keys())


def get_invest_period(select_group):
    idx = GROUP_KEYS.index(select_group)
    if idx + 1 >= len(GROUP_KEYS):
        return None
    next_group = GROUP_KEYS[idx + 1]
    return next_group, GROUP_PERIODS[next_group]


# ─────────────────────────────────────────────
# 가격 및 수익률
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


def get_period_return(ticker, start, end, method="close"):
    try:
        df = fdr.DataReader(ticker, start, end)
        if df.empty or len(df) < 2:
            print(f"    [경고] {ticker}: 데이터 부족")
            return 0
        entry, exit_ = _get_entry_exit_price(df, method)
        if entry == 0:
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
# 그룹별 상세 검증
# ─────────────────────────────────────────────
def inspect_details(price_method="close"):
    available_csvs = sorted(
        [f.replace('.csv', '') for f in os.listdir(BASE_DIR) if f.endswith('.csv')],
        key=lambda x: int(x.replace('g', ''))
    )

    for select_group in available_csvs:
        invest_info = get_invest_period(select_group)
        if invest_info is None:
            continue
        invest_group, (start_date, end_date) = invest_info

        csv_path = os.path.join(BASE_DIR, f"{select_group}.csv")
        df = pd.read_csv(csv_path)
        df['티커'] = df['티커'].astype(str).str.zfill(6)

        w_eq = calc_equal_weight(df)
        w_sc = calc_score_weight(df)

        print(f"\n{'=' * 100}")
        print(f"  {select_group} 선정 → {invest_group} 투자 ({start_date} ~ {end_date})"
              f"  |  {PRICE_LABEL[price_method]}  |  {args.signal}")
        print(f"{'=' * 100}")

        header = (f"  {'':2s} {'종목명':12s} | {'수익률':>8s} | "
                  f"{'동일비중':>8s} {'기여도':>8s} | "
                  f"{'점수비중':>8s} {'기여도':>8s} | {'비고'}")
        print(header)
        print(f"  {'-' * 93}")

        total_ew = 0
        total_sw = 0

        for i, (_, row) in enumerate(df.iterrows()):
            ret = get_period_return(row['티커'], start_date, end_date, method=price_method)

            c_ew = ret * w_eq.iloc[i]
            c_sw = ret * w_sc.iloc[i]
            total_ew += c_ew
            total_sw += c_sw

            mark = "**" if '중복' in str(row['비고']) else "  "
            print(f"  {mark} {row['종목명']:12s} | "
                  f"{ret*100:+7.2f}% | "
                  f"{w_eq.iloc[i]*100:6.1f}% {c_ew*100:+7.3f}% | "
                  f"{w_sc.iloc[i]*100:6.1f}% {c_sw*100:+7.3f}% | "
                  f"{row['비고']}")

        print(f"  {'-' * 93}")
        print(f"  >>> 동일비중: {total_ew*100:+.2f}%  |  점수비중: {total_sw*100:+.2f}%  |  "
              f"차이: {(total_sw - total_ew)*100:+.2f}%p")


if __name__ == "__main__":
    inspect_details(price_method=args.price)
