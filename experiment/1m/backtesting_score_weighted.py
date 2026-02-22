import pandas as pd
import numpy as np
import FinanceDataReader as fdr
import matplotlib.pyplot as plt
import os
import argparse
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# 1. 실행 인자 설정
# 사용법: python backtesting_score_weighted.py --cap 5천억 --price close
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="수급 강도 전략 백테스팅 - 동일비중 vs 점수비중 비교")
parser.add_argument("--cap", type=str, default="5천억", choices=["2천억", "5천억"],
                    help="분석할 시총 폴더 선택")
parser.add_argument("--price", type=str, default="close",
                    choices=["open", "close", "vwap"],
                    help="수익률 계산 기준 (open/close/vwap)")
args = parser.parse_args()

PRICE_LABEL = {"open": "시가(Open)", "close": "종가(Close)", "vwap": "VWAP"}

BASE_DIR = os.path.join(os.path.dirname(__file__), f"../../data/file/monthly_csv_data/시총{args.cap}")
KOSPI = "KS11"
INVEST_YEAR = 2025
RISK_FREE_ANNUAL = 0.03


# ─────────────────────────────────────────────
# 2. 가격 및 수익률 계산
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


def get_monthly_return(ticker, start, end, method="close"):
    try:
        df = fdr.DataReader(ticker, start, end)
        if df.empty or len(df) < 2:
            print(f"  [경고] {ticker}: 데이터 부족")
            return 0
        entry, exit_ = _get_entry_exit_price(df, method)
        if entry == 0:
            return 0
        return (exit_ / entry) - 1
    except Exception as e:
        print(f"  [에러] {ticker}: {e}")
        return 0


# ─────────────────────────────────────────────
# 3. 비중 계산 방식 2가지
# ─────────────────────────────────────────────
def calc_equal_weight(df):
    """기존 방식: 동일비중 + 중복 2배"""
    df['score'] = df['비고'].apply(lambda x: 2 if '중복' in str(x) else 1)
    df['weight'] = df['score'] / df['score'].sum()
    return df['weight']


def calc_score_weight(df):
    """신규 방식: 최종점수 정규화 비중"""
    scores = df['최종점수'].clip(lower=0)  # 음수 점수 방지
    total = scores.sum()
    if total == 0:
        return pd.Series(1 / len(df), index=df.index)
    return scores / total


# ─────────────────────────────────────────────
# 4. 성과 지표 계산
# ─────────────────────────────────────────────
def calc_sharpe(monthly_returns, rf_annual=RISK_FREE_ANNUAL):
    rf_m = (1 + rf_annual) ** (1 / 12) - 1
    excess = monthly_returns - rf_m
    return (excess.mean() / excess.std()) * np.sqrt(12) if excess.std() != 0 else 0


def calc_mdd(monthly_returns):
    cum = (1 + monthly_returns).cumprod()
    return ((cum - cum.cummax()) / cum.cummax()).min()


def calc_ir(strategy_ret, bench_ret):
    excess = strategy_ret - bench_ret
    return (excess.mean() / excess.std()) * np.sqrt(12) if excess.std() != 0 else 0


def calc_win_rate(strategy_ret, bench_ret):
    wins = (strategy_ret > bench_ret).sum()
    return wins / len(strategy_ret) if len(strategy_ret) > 0 else 0


def summarize_metrics(label, s_ret, b_ret):
    return {
        '전략명': label,
        '총 수익률': f"{((1 + s_ret).prod() - 1) * 100:.2f}%",
        'KOSPI 총 수익률': f"{((1 + b_ret).prod() - 1) * 100:.2f}%",
        '초과수익률': f"{(((1+s_ret).prod() - 1) - ((1+b_ret).prod() - 1)) * 100:.2f}%p",
        '샤프 비율': f"{calc_sharpe(s_ret):.3f}",
        'MDD': f"{calc_mdd(s_ret) * 100:.2f}%",
        '정보 비율 (IR)': f"{calc_ir(s_ret, b_ret):.3f}",
        '월간 승률': f"{calc_win_rate(s_ret, b_ret) * 100:.1f}% ({(s_ret > b_ret).sum()}/{len(s_ret)})",
        '월평균 수익률': f"{s_ret.mean() * 100:.2f}%",
        '월 변동성': f"{s_ret.std() * 100:.2f}%",
    }


# ─────────────────────────────────────────────
# 5. 백테스팅 메인 로직 (두 전략 동시 실행)
# ─────────────────────────────────────────────
def run_comparison_backtest(price_method="close"):
    all_files = sorted([f for f in os.listdir(BASE_DIR) if f.endswith('.csv')])

    monthly_results = []

    for file_name in all_files:
        try:
            month_str = file_name.split('_')[1].replace('월', '')
            select_month = int(month_str)
        except Exception:
            continue

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

        df = pd.read_csv(os.path.join(BASE_DIR, file_name))
        df['티커'] = df['티커'].astype(str).str.zfill(6)

        # 두 가지 비중 계산
        w_equal = calc_equal_weight(df)
        w_score = calc_score_weight(df)

        print(f"\n>>> {year}년 {invest_month:02d}월 (선정: {select_month}월 | {PRICE_LABEL[price_method]})")

        # 비중 분포 요약
        print(f"    [동일비중] 최대 {w_equal.max()*100:.1f}% / 최소 {w_equal.min()*100:.1f}%"
              f"  |  [점수비중] 최대 {w_score.max()*100:.1f}% / 최소 {w_score.min()*100:.1f}%")

        # 각 종목 수익률 한 번만 조회 (API 호출 절약)
        stock_returns = []
        for _, row in df.iterrows():
            ret = get_monthly_return(row['티커'], start_date, end_date, method=price_method)
            stock_returns.append(ret)

        stock_returns = np.array(stock_returns)

        ret_equal = np.dot(stock_returns, w_equal.values)
        ret_score = np.dot(stock_returns, w_score.values)
        ret_bench = get_monthly_return(KOSPI, start_date, end_date, method=price_method)

        monthly_results.append({
            'Date': f"{year}-{invest_month:02d}",
            'EqualWeight': ret_equal,
            'ScoreWeight': ret_score,
            'KOSPI': ret_bench
        })

    res = pd.DataFrame(monthly_results)
    res['EW_Cum'] = (1 + res['EqualWeight']).cumprod() - 1
    res['SW_Cum'] = (1 + res['ScoreWeight']).cumprod() - 1
    res['KOSPI_Cum'] = (1 + res['KOSPI']).cumprod() - 1

    metrics_ew = summarize_metrics("동일비중 (중복2배)", res['EqualWeight'], res['KOSPI'])
    metrics_sw = summarize_metrics("점수비중 (최종점수)", res['ScoreWeight'], res['KOSPI'])

    return res, metrics_ew, metrics_sw


# ─────────────────────────────────────────────
# 6. 실행 및 출력
# ─────────────────────────────────────────────
if __name__ == "__main__":
    result, m_ew, m_sw = run_comparison_backtest(price_method=args.price)

    # ── 월별 수익률 테이블 ──
    print("\n" + "=" * 90)
    print(f"  2025년 액티브 ETF - 비중 방식 비교  [시총 {args.cap} / {PRICE_LABEL[args.price]}]")
    print("=" * 90)

    disp = result[['Date']].copy()
    disp['동일비중'] = result['EqualWeight'].apply(lambda x: f"{x*100:+.2f}%")
    disp['점수비중'] = result['ScoreWeight'].apply(lambda x: f"{x*100:+.2f}%")
    disp['KOSPI'] = result['KOSPI'].apply(lambda x: f"{x*100:+.2f}%")
    disp['동일비중(누적)'] = result['EW_Cum'].apply(lambda x: f"{x*100:+.2f}%")
    disp['점수비중(누적)'] = result['SW_Cum'].apply(lambda x: f"{x*100:+.2f}%")
    disp['KOSPI(누적)'] = result['KOSPI_Cum'].apply(lambda x: f"{x*100:+.2f}%")
    print(disp.to_string(index=False))

    # ── 성과 지표 비교 ──
    print("\n" + "-" * 90)
    print("  [ 성과 지표 비교 ]")
    print("-" * 90)
    header = f"  {'지표':28s} | {'동일비중 (중복2배)':>18s} | {'점수비중 (최종점수)':>18s}"
    print(header)
    print("  " + "-" * 70)
    for key in list(m_ew.keys())[1:]:  # '전략명' 제외
        print(f"  {key:28s} | {m_ew[key]:>18s} | {m_sw[key]:>18s}")
    print("-" * 90)

    # ── 그래프 시각화 ──
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]})
    fig.suptitle(f'비중 방식 비교: 동일비중 vs 점수비중  [{args.cap} / {PRICE_LABEL[args.price]}]',
                 fontsize=14, fontweight='bold')

    # (상단) 누적 수익률
    ax1 = axes[0]
    ax1.plot(result['Date'], result['EW_Cum'] * 100,
             label='동일비중 (중복2배)', marker='o', linewidth=2, color='#2196F3')
    ax1.plot(result['Date'], result['SW_Cum'] * 100,
             label='점수비중 (최종점수)', marker='s', linewidth=2, color='#FF9800')
    ax1.plot(result['Date'], result['KOSPI_Cum'] * 100,
             label='KOSPI', linestyle='--', linewidth=2, color='#9E9E9E')
    ax1.set_ylabel('누적 수익률 (%)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # (하단) 두 전략 월별 수익률 차이 (점수비중 - 동일비중)
    ax2 = axes[1]
    diff = (result['ScoreWeight'] - result['EqualWeight']) * 100
    colors = ['#FF9800' if x >= 0 else '#2196F3' for x in diff]
    ax2.bar(result['Date'], diff, color=colors, alpha=0.8)
    ax2.axhline(y=0, color='black', linewidth=0.8)
    ax2.set_ylabel('점수비중 - 동일비중 (%p)')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = f"result_comparison_{args.cap}_{args.price}.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n>> 비교 백테스팅 완료! 그래프가 '{output_file}'로 저장되었습니다.")
