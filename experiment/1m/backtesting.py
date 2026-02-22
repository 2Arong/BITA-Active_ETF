import pandas as pd
import numpy as np
import FinanceDataReader as fdr
import matplotlib.pyplot as plt
import os
import argparse
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# 1. 실행 인자 설정 (argparse)
# 사용법: python backtesting.py --cap 5천억 --price open
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser(description="수급 강도 전략 1년 백테스팅")
parser.add_argument("--cap", type=str, default="5천억", choices=["2천억", "5천억"],
                    help="분석할 시총 폴더 선택 (2천억 또는 5천억)")
parser.add_argument("--price", type=str, default="close",
                    choices=["open", "close", "vwap"],
                    help="수익률 계산 기준 (open: 시가, close: 종가, vwap: 거래량가중평균)")
args = parser.parse_args()

PRICE_LABEL = {"open": "시가(Open) 기준", "close": "종가(Close) 기준", "vwap": "VWAP 기준"}

# 설정 값
BASE_DIR = os.path.join(os.path.dirname(__file__), f"../../data/file/monthly_csv_data/시총{args.cap}")
KOSPI = "KS11"  # 코스피 벤치마크 기호
INVEST_YEAR = 2025
RISK_FREE_ANNUAL = 0.03  # 연 무위험 수익률 (한국 국채 3년물 기준 약 3%)

# ─────────────────────────────────────────────
# 2. 수익률 계산 함수 (시가 / 종가 / VWAP)
# ─────────────────────────────────────────────
def _get_entry_exit_price(df_price, method):
    """주어진 OHLCV 데이터에서 매수가/매도가를 반환"""
    if method == "open":
        entry = df_price['Open'].iloc[0]
        exit_ = df_price['Open'].iloc[-1]  # 마지막 날 시가에 매도(다음 달 첫날 시가 대용)
    elif method == "close":
        entry = df_price['Close'].iloc[0]
        exit_ = df_price['Close'].iloc[-1]
    elif method == "vwap":
        # VWAP 근사치: 일별 (High + Low + Close) / 3 을 거래량 가중 평균
        typical = (df_price['High'] + df_price['Low'] + df_price['Close']) / 3
        volume = df_price['Volume']
        # 첫 날 VWAP (단일 일이므로 typical price)
        entry = typical.iloc[0]
        # 마지막 날 VWAP
        exit_ = typical.iloc[-1]
    else:
        raise ValueError(f"지원하지 않는 가격 기준: {method}")
    return entry, exit_


def get_monthly_return(ticker, start, end, method="close"):
    """특정 기간의 수익률을 지정된 가격 기준으로 계산"""
    try:
        df = fdr.DataReader(ticker, start, end)
        if df.empty or len(df) < 2:
            print(f"  [경고] {ticker}: 데이터 부족 (행 수: {len(df) if not df.empty else 0})")
            return 0
        entry, exit_ = _get_entry_exit_price(df, method)
        if entry == 0:
            print(f"  [경고] {ticker}: 매수가가 0")
            return 0
        return (exit_ / entry) - 1
    except Exception as e:
        print(f"  [에러] {ticker}: {e}")
        return 0


# ─────────────────────────────────────────────
# 3. 성과 지표 계산 함수
# ─────────────────────────────────────────────
def calc_sharpe_ratio(monthly_returns, risk_free_annual=RISK_FREE_ANNUAL):
    """월간 수익률 기반 연율화 샤프 비율"""
    rf_monthly = (1 + risk_free_annual) ** (1 / 12) - 1
    excess = monthly_returns - rf_monthly
    if excess.std() == 0:
        return 0
    return (excess.mean() / excess.std()) * np.sqrt(12)


def calc_mdd(monthly_returns):
    """월간 수익률 시계열 기반 MDD (최대 낙폭)"""
    cumulative = (1 + monthly_returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return drawdown.min()  # 음수값 (가장 큰 낙폭)


def calc_information_ratio(strategy_returns, benchmark_returns):
    """정보 비율 (연율화): 초과수익 평균 / 초과수익 표준편차 * sqrt(12)"""
    excess = strategy_returns - benchmark_returns
    if excess.std() == 0:
        return 0
    return (excess.mean() / excess.std()) * np.sqrt(12)


def calc_win_rate(strategy_returns, benchmark_returns):
    """월간 승률: 전략이 벤치마크를 이긴 달의 비율"""
    wins = (strategy_returns > benchmark_returns).sum()
    total = len(strategy_returns)
    return wins / total if total > 0 else 0


# ─────────────────────────────────────────────
# 4. 백테스팅 메인 로직
# ─────────────────────────────────────────────
def run_full_year_backtest(price_method="close"):
    # 폴더 내의 CSV 파일들 읽기 (파일명: 2025_01월_... 순서대로)
    all_files = sorted([f for f in os.listdir(BASE_DIR) if f.endswith('.csv')])

    monthly_results = []

    for file_name in all_files:
        # 1. 파일명에서 해당 '선정 월' 추출
        try:
            month_str = file_name.split('_')[1].replace('월', '')
            select_month = int(month_str)
        except Exception:
            continue

        # 2. 실제 투자 기간 설정 (N월 선정 -> N+1월 투자)
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

        # 3. 데이터 로드 및 비중 계산 (중복 2배)
        df = pd.read_csv(os.path.join(BASE_DIR, file_name))
        df['티커'] = df['티커'].astype(str).str.zfill(6)
        df['score'] = df['비고'].apply(lambda x: 2 if '중복' in str(x) else 1)
        df['weight'] = df['score'] / df['score'].sum()

        print(f"\n>>> {year}년 {invest_month:02d}월 수익률 계산 중... "
            f"(선정: {select_month}월 | 기준: {PRICE_LABEL[price_method]})")

        # 4. 전략 수익률 vs 코스피 수익률
        strategy_ret = 0
        for _, row in df.iterrows():
            ret = get_monthly_return(row['티커'], start_date, end_date, method=price_method)
            strategy_ret += ret * row['weight']

        benchmark_ret = get_monthly_return(KOSPI, start_date, end_date, method=price_method)

        monthly_results.append({
            'Date': f"{year}-{invest_month:02d}",
            'Strategy': strategy_ret,
            'KOSPI': benchmark_ret
        })

    # ── 5. 성과 지표 계산 ──
    res_df = pd.DataFrame(monthly_results)
    res_df['Strategy_Cum'] = (1 + res_df['Strategy']).cumprod() - 1
    res_df['KOSPI_Cum'] = (1 + res_df['KOSPI']).cumprod() - 1
    res_df['Alpha'] = (res_df['Strategy_Cum'] - res_df['KOSPI_Cum']) * 100  # %p 단위

    # 핵심 지표 계산
    s_ret = res_df['Strategy']
    b_ret = res_df['KOSPI']

    metrics = {
        '전략 총 수익률': f"{res_df['Strategy_Cum'].iloc[-1] * 100:.2f}%",
        'KOSPI 총 수익률': f"{res_df['KOSPI_Cum'].iloc[-1] * 100:.2f}%",
        '초과수익률 (Alpha)': f"{(res_df['Strategy_Cum'].iloc[-1] - res_df['KOSPI_Cum'].iloc[-1]) * 100:.2f}%p",
        '샤프 비율 (전략)': f"{calc_sharpe_ratio(s_ret):.3f}",
        '샤프 비율 (KOSPI)': f"{calc_sharpe_ratio(b_ret):.3f}",
        'MDD (전략)': f"{calc_mdd(s_ret) * 100:.2f}%",
        'MDD (KOSPI)': f"{calc_mdd(b_ret) * 100:.2f}%",
        '정보 비율 (IR)': f"{calc_information_ratio(s_ret, b_ret):.3f}",
        '월간 승률': f"{calc_win_rate(s_ret, b_ret) * 100:.1f}% ({(s_ret > b_ret).sum()}/{len(s_ret)})",
        '월평균 수익률 (전략)': f"{s_ret.mean() * 100:.2f}%",
        '월평균 수익률 (KOSPI)': f"{b_ret.mean() * 100:.2f}%",
        '월 수익률 표준편차 (전략)': f"{s_ret.std() * 100:.2f}%",
    }

    return res_df, metrics


# ─────────────────────────────────────────────
# 5. 실행 및 출력
# ─────────────────────────────────────────────
if __name__ == "__main__":
    result, metrics = run_full_year_backtest(price_method=args.price)

    # ── 월별 수익률 테이블 ──
    print("\n" + "=" * 70)
    print(f"  2025년 액티브 ETF 모델 성과 보고서")
    print(f"  시총: {args.cap} | 가격 기준: {PRICE_LABEL[args.price]}")
    print("=" * 70)

    display_df = result.copy()
    for col in ['Strategy', 'KOSPI', 'Strategy_Cum', 'KOSPI_Cum']:
        display_df[col] = display_df[col].apply(lambda x: f"{x * 100:.2f}%")
    display_df['Alpha'] = result['Alpha'].apply(lambda x: f"{x:.2f}%p")
    print(display_df.to_string(index=False))

    # ── 성과 지표 요약 ──
    print("\n" + "-" * 70)
    print("  [ 핵심 성과 지표 ]")
    print("-" * 70)
    for k, v in metrics.items():
        print(f"  {k:30s} : {v}")
    print("-" * 70)

    # ── 그래프 시각화 (2개 서브플롯) ──
    plt.rcParams['font.family'] ='Malgun Gothic'
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]})
    fig.suptitle(f'Active ETF Strategy vs KOSPI  [{args.cap} / {PRICE_LABEL[args.price]}]',
                 fontsize=15, fontweight='bold')

    # (상단) 누적 수익률 그래프
    ax1 = axes[0]
    ax1.plot(result['Date'], result['Strategy_Cum'] * 100,
             label='My Active ETF', marker='o', linewidth=2, color='#2196F3')
    ax1.plot(result['Date'], result['KOSPI_Cum'] * 100,
             label='KOSPI (Benchmark)', linestyle='--', linewidth=2, color='#F44336')
    ax1.fill_between(result['Date'],
                     result['Strategy_Cum'] * 100,
                     result['KOSPI_Cum'] * 100,
                     alpha=0.15, color='green',
                     where=result['Strategy_Cum'] >= result['KOSPI_Cum'], label='Alpha (+)')
    ax1.fill_between(result['Date'],
                     result['Strategy_Cum'] * 100,
                     result['KOSPI_Cum'] * 100,
                     alpha=0.15, color='red',
                     where=result['Strategy_Cum'] < result['KOSPI_Cum'], label='Alpha (-)')
    ax1.set_ylabel('Cumulative Return (%)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # (하단) 월별 초과수익률 바 차트
    ax2 = axes[1]
    excess = (result['Strategy'] - result['KOSPI']) * 100
    colors = ['#4CAF50' if x >= 0 else '#F44336' for x in excess]
    ax2.bar(result['Date'], excess, color=colors, alpha=0.8)
    ax2.axhline(y=0, color='black', linewidth=0.8)
    ax2.set_ylabel('Monthly Excess Return (%p)')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = f"result_{args.cap}_{args.price}.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n>> 백테스팅 완료! 그래프가 '{output_file}'로 저장되었습니다.")
