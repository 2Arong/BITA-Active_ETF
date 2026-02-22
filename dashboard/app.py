import sys
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_DIR, "../experiment/2w"))

from datetime import date, datetime

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import FinanceDataReader as fdr

from backtesting_2w import (
    GROUP_PERIODS, GROUP_KEYS, PRICE_LABEL,
    run_backtest, calc_sharpe, calc_mdd, calc_ir, calc_win_rate,
)

NAV_BASE = 10_000

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Ko-ActiveETF 대시보드",
    page_icon="📈",
    layout="wide",
)

st.markdown("""
<style>
    .nav-card {
        background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
        padding: 1.6rem 2rem; border-radius: 1rem; color: white;
    }
    .nav-card .etf-name { font-size: 0.9rem; opacity: 0.8; margin: 0; }
    .nav-card .nav-price { font-size: 2.6rem; font-weight: 700; margin: 0.3rem 0 0 0; }
    .nav-card .nav-change { font-size: 1rem; margin-top: 0.2rem; }
    .section-title {
        font-size: 1.15rem; font-weight: 600;
        border-left: 4px solid #1a237e; padding-left: 0.6rem;
        margin-top: 2rem; margin-bottom: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 헬퍼 함수
# ─────────────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def get_sector_map():
    """KRX 종목 상세 리스트에서 티커 → 업종 매핑을 반환한다."""
    try:
        listing = fdr.StockListing("KRX-DESC")
        listing["Code"] = listing["Code"].astype(str).str.zfill(6)
        return dict(zip(listing["Code"], listing["Sector"]))
    except Exception:
        pass
    return {}


def calc_window_return(series, n):
    """series(기간 수익률)의 마지막 n개 기간의 누적 수익률."""
    if n is None or n >= len(series):
        return float((1 + series).prod() - 1)
    tail = series.iloc[-n:]
    return float((1 + tail).prod() - 1)


def parse_bigo_type(bigo: str) -> str:
    """비고 컬럼에서 선정 유형을 파싱."""
    s = str(bigo)
    if "중복" in s:
        return "중복선정 (단기+장기)"
    if "단기" in s:
        return "단기상위"
    return "장기상위"


def fmt_pct(v, sign=True):
    if sign:
        return f"{v * 100:+.2f}%"
    return f"{v * 100:.2f}%"


def group_to_date_label(g):
    """g1 → '01.02~01.15' 형태의 짧은 날짜 레이블 반환."""
    period = GROUP_PERIODS.get(g)
    if not period:
        return g
    s = period[0][5:]
    e = period[1][5:]
    return f"{s.replace('-', '.')}~{e.replace('-', '.')}"


def date_to_group(d, group_list):
    """date 객체를 받아, 해당 날짜가 포함되는 투자 그룹을 반환한다."""
    for g in group_list:
        period = GROUP_PERIODS.get(g)
        if not period:
            continue
        s = datetime.strptime(period[0], "%Y-%m-%d").date()
        e = datetime.strptime(period[1], "%Y-%m-%d").date()
        if s <= d <= e:
            return g
    return group_list[-1]


SIGNAL_TYPE = "외국인단독"


# ─────────────────────────────────────────────
# 캐싱 백테스팅
# ─────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def cached_backtest(signal):
    base_dir = os.path.join(_DIR, f"../data/file/rebal_2w_csv/{signal}")
    return run_backtest(base_dir, price_method="close")


# ─────────────────────────────────────────────
# 메인 (페이지 로드 시 자동 실행)
# ─────────────────────────────────────────────
if "result" not in st.session_state:
    with st.spinner("백테스팅 실행 중... (첫 실행 시 1~3분 소요)"):
        res, m_eq, m_sc, m_ka, holdings = cached_backtest(SIGNAL_TYPE)
    st.session_state.update({
        "result": res, "m_eq": m_eq, "m_sc": m_sc, "m_ka": m_ka,
        "holdings": holdings,
    })

res = st.session_state["result"]
holdings = st.session_state["holdings"]
sig_label = SIGNAL_TYPE

ret_col = "EqualWeight"
cum_col = "EW_Cum"
w_col = "w_equal"
contrib_col = "contrib_eq"
strategy_label = "동일비중"

s_ret = res[ret_col]
n = len(s_ret)

nav_series = NAV_BASE * (1 + s_ret).cumprod()
last_nav = float(nav_series.iloc[-1])
prev_nav = float(nav_series.iloc[-2]) if n >= 2 else NAV_BASE
nav_change = last_nav - prev_nav
nav_change_pct = nav_change / prev_nav
total_ret = (last_nav / NAV_BASE) - 1

invest_groups = list(holdings.keys())
latest_group = invest_groups[-1]
latest_holdings = holdings[latest_group]

# =========================================================
# 섹션 1: 상단 헤더 — 기준 가격 카드
# =========================================================
last_period = GROUP_PERIODS.get(latest_group, ("", ""))
change_color = "#e53935" if nav_change >= 0 else "#1e88e5"
change_arrow = "▲" if nav_change >= 0 else "▼"

st.markdown(f"""
<div class="nav-card">
    <p class="etf-name">Ko-ActiveETF 수급 강도 한국형 액티브 — {sig_label} / {strategy_label}</p>
    <p class="nav-price">{last_nav:,.0f}원</p>
    <p class="nav-change" style="color:{change_color}">
        전 기간 대비 {change_arrow} {abs(nav_change):,.0f}원 ({nav_change_pct:+.2%})
        &nbsp;&nbsp;|&nbsp;&nbsp;설정일 이후 {total_ret:+.2%}
    </p>
    <p style="font-size:0.75rem; opacity:0.6; margin-top:0.4rem;">
        기준일: {last_period[1]} &nbsp;|&nbsp; 설정일: {GROUP_PERIODS[invest_groups[0]][0]}
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("")

# =========================================================
# 섹션 2: 수익률 (탭 버튼)
# =========================================================
st.markdown('<p class="section-title">수익률</p>', unsafe_allow_html=True)

period_config = {
    "1년": None,
    "6개월": 13,
    "3개월": 6,
    "1개월": 2,
}

tab_labels = list(period_config.keys())
tabs = st.tabs(tab_labels)

for tab, (label, win) in zip(tabs, period_config.items()):
    with tab:
        ret_my = calc_window_return(s_ret, win)
        ret_kospi = calc_window_return(res["KOSPI"], win)
        ret_k200 = calc_window_return(res["KOSPI200"], win)
        ret_koact = calc_window_return(res["KoAct"], win)

        rc1, rc2, rc3, rc4 = st.columns(4)
        delta_vs_kospi = (ret_my - ret_kospi) * 100
        rc1.metric("My ETF", fmt_pct(ret_my), f"{delta_vs_kospi:+.1f}%p vs KOSPI")
        rc2.metric("KOSPI", fmt_pct(ret_kospi))
        rc3.metric("KOSPI 200", fmt_pct(ret_k200))
        rc4.metric("KoAct 배당성장", fmt_pct(ret_koact))

        tail_n = win if (win is not None and win < n) else n
        tail_nav = NAV_BASE * (1 + s_ret.iloc[-tail_n:]).cumprod()
        tail_kospi = NAV_BASE * (1 + res["KOSPI"].iloc[-tail_n:]).cumprod()
        tail_k200 = NAV_BASE * (1 + res["KOSPI200"].iloc[-tail_n:]).cumprod()
        tail_dates = res["EndDate"].iloc[-tail_n:]

        fig_tab = go.Figure()
        fig_tab.add_trace(go.Scatter(
            x=tail_dates, y=tail_nav, mode="lines+markers",
            name="My ETF", line=dict(color="#1a237e", width=2.5), marker=dict(size=4),
        ))
        fig_tab.add_trace(go.Scatter(
            x=tail_dates, y=tail_kospi, mode="lines", name="KOSPI",
            line=dict(color="#9E9E9E", width=1.5, dash="dash"),
        ))
        fig_tab.add_trace(go.Scatter(
            x=tail_dates, y=tail_k200, mode="lines", name="KOSPI 200",
            line=dict(color="#607D8B", width=1.5, dash="dash"),
        ))
        fig_tab.update_layout(
            height=280, yaxis_title="기준가격 (원)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            hovermode="x unified",
            margin=dict(l=20, r=20, t=30, b=20),
        )
        st.plotly_chart(fig_tab, use_container_width=True)

# =========================================================
# 섹션 3: 기준 가격 및 기초 지수 차트
# =========================================================
st.markdown('<p class="section-title">기준 가격 및 기초 지수</p>', unsafe_allow_html=True)

nav_kospi = NAV_BASE * (1 + res["KOSPI"]).cumprod()
nav_k200 = NAV_BASE * (1 + res["KOSPI200"]).cumprod()
nav_koact = NAV_BASE * (1 + res["KoAct"]).cumprod()
x_dates = res["EndDate"]

fig_nav = go.Figure()
fig_nav.add_trace(go.Scatter(
    x=x_dates, y=nav_series, mode="lines+markers",
    name=f"My ETF ({strategy_label})",
    line=dict(color="#1a237e", width=2.5), marker=dict(size=4),
    hovertemplate="%{x}<br>%{y:,.0f}원<extra></extra>",
))
fig_nav.add_trace(go.Scatter(
    x=x_dates, y=nav_kospi, mode="lines", name="KOSPI",
    line=dict(color="#9E9E9E", width=1.5, dash="dash"),
    hovertemplate="%{x}<br>%{y:,.0f}원<extra></extra>",
))
fig_nav.add_trace(go.Scatter(
    x=x_dates, y=nav_k200, mode="lines", name="KOSPI 200",
    line=dict(color="#607D8B", width=1.5, dash="dash"),
    hovertemplate="%{x}<br>%{y:,.0f}원<extra></extra>",
))
fig_nav.add_trace(go.Scatter(
    x=x_dates, y=nav_koact, mode="lines", name="KoAct 배당성장",
    line=dict(color="#8E24AA", width=1.5, dash="dashdot"),
    hovertemplate="%{x}<br>%{y:,.0f}원<extra></extra>",
))
fig_nav.add_hline(y=NAV_BASE, line_dash="dot", line_color="gray",
                  annotation_text=f"기준가 {NAV_BASE:,}원")
fig_nav.update_layout(
    height=420, yaxis_title="기준가격 (원)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    hovermode="x unified",
    margin=dict(l=20, r=20, t=40, b=20),
)
st.plotly_chart(fig_nav, use_container_width=True)

# =========================================================
# 섹션 4 & 5: 자산 구성 내역 / 종목별 비중 TOP5 (좌우 배치)
# =========================================================
col_comp, col_stock = st.columns(2)

# — 자산 구성 내역
with col_comp:
    st.markdown('<p class="section-title">자산 구성 내역</p>', unsafe_allow_html=True)
    st.caption(f"기준 기간: {last_period[0]} ~ {last_period[1]}")

    h = latest_holdings.copy()
    h["선정유형"] = h["비고"].apply(parse_bigo_type)
    h["비중"] = h[w_col]
    type_weights = h.groupby("선정유형")["비중"].sum().sort_values(ascending=False)

    fig_comp = px.pie(
        names=type_weights.index,
        values=type_weights.values,
        hole=0.45,
        color_discrete_sequence=["#1a237e", "#42a5f5", "#90caf9"],
    )
    fig_comp.update_traces(textposition="inside", textinfo="percent+label",
                           textfont_size=11)
    fig_comp.update_layout(
        height=300, margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig_comp, use_container_width=True)

    comp_df = pd.DataFrame({
        "선정유형": type_weights.index,
        "비중": type_weights.values,
    })
    comp_df["비중"] = comp_df["비중"].map(lambda v: f"{v * 100:.1f}%")
    st.dataframe(comp_df, use_container_width=True, hide_index=True)

# — 종목별 비중 TOP5
with col_stock:
    st.markdown('<p class="section-title">주식 종목별 비중 TOP5</p>', unsafe_allow_html=True)
    st.caption(f"기준 기간: {last_period[0]} ~ {last_period[1]}")

    top5_stocks = h.nlargest(5, w_col)[["종목명", w_col]].copy()
    top5_stocks["비중(%)"] = top5_stocks[w_col] * 100

    fig_stock = px.pie(
        names=top5_stocks["종목명"],
        values=top5_stocks["비중(%)"],
        hole=0.45,
        color_discrete_sequence=["#1a237e", "#283593", "#3949ab", "#5c6bc0", "#7986cb"],
    )
    fig_stock.update_traces(
        textposition="inside", textinfo="percent+label", textfont_size=11,
        hovertemplate="%{label}<br>비중: %{value:.1f}%<extra></extra>",
    )
    fig_stock.update_layout(
        height=300, margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig_stock, use_container_width=True)

    disp_stock = top5_stocks[["종목명"]].copy()
    disp_stock["비중"] = top5_stocks[w_col].map(lambda v: f"{v * 100:.1f}%")
    st.dataframe(disp_stock, use_container_width=True, hide_index=True)

# =========================================================
# 섹션 6: 업종별 비중 TOP5
# =========================================================
st.markdown('<p class="section-title">주식 업종별 비중 TOP5</p>', unsafe_allow_html=True)
st.caption(f"기준 기간: {last_period[0]} ~ {last_period[1]}")

sector_map = get_sector_map()

h_sector = latest_holdings.copy()
h_sector["업종"] = h_sector["티커"].map(sector_map).fillna("기타")
h_sector["비중"] = h_sector[w_col]
sector_weights = h_sector.groupby("업종")["비중"].sum().sort_values(ascending=False).head(5)

sector_stocks = {}
for sec in sector_weights.index:
    names = h_sector[h_sector["업종"] == sec]["종목명"].tolist()
    sector_stocks[sec] = ", ".join(names)

col_sec_chart, col_sec_tbl = st.columns([3, 2])
with col_sec_chart:
    fig_sector = go.Figure(go.Bar(
        x=sector_weights.values[::-1],
        y=sector_weights.index[::-1],
        orientation="h",
        marker_color="#42a5f5",
        text=[f"{v * 100:.1f}%" for v in sector_weights.values[::-1]],
        textposition="auto",
    ))
    fig_sector.update_layout(
        height=300, xaxis_title="비중",
        xaxis_tickformat=".0%",
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig_sector, use_container_width=True)

with col_sec_tbl:
    sec_df = pd.DataFrame({
        "업종": sector_weights.index,
        "비중": sector_weights.values,
        "종목": [sector_stocks[s] for s in sector_weights.index],
    })
    sec_df["비중"] = sec_df["비중"].map(lambda v: f"{v * 100:.1f}%")
    st.dataframe(sec_df, use_container_width=True, hide_index=True)

# =========================================================
# 섹션 7: 성과 지표 카드
# =========================================================
st.markdown('<p class="section-title">성과 지표</p>', unsafe_allow_html=True)

b_ret = res["KOSPI"]
sharpe = calc_sharpe(s_ret, periods_per_year=n)
mdd = calc_mdd(s_ret) * 100
ir = calc_ir(s_ret, b_ret, periods_per_year=n)
win = calc_win_rate(s_ret, b_ret) * 100

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("총 수익률", fmt_pct(total_ret, sign=False),
          f"{(total_ret - calc_window_return(b_ret, None)) * 100:+.1f}%p vs KOSPI")
c2.metric("샤프 비율", f"{sharpe:.2f}")
c3.metric("MDD", f"{mdd:.1f}%")
c4.metric("정보비율 (IR)", f"{ir:.2f}")
c5.metric("승률 (vs KOSPI)", f"{win:.0f}%", f"{int((s_ret > b_ret).sum())}/{n}")

# =========================================================
# 섹션 8: 기간별 초과수익 바차트
# =========================================================
st.markdown('<p class="section-title">기간별 초과수익</p>', unsafe_allow_html=True)

excess = (res[ret_col] - res["KOSPI"]) * 100
x_labels = [group_to_date_label(g) for g in res["InvestGroup"]]
fig_excess = go.Figure(go.Bar(
    x=x_labels, y=excess,
    marker_color=[("#4CAF50" if v >= 0 else "#F44336") for v in excess],
    hovertemplate="%{x}<br>초과수익: %{y:+.4f}%p<extra></extra>",
))
fig_excess.add_hline(y=0, line_color="black", line_width=1)
fig_excess.update_layout(
    height=250, yaxis_title="초과수익 (%p vs KOSPI)",
    xaxis=dict(tickangle=-45),
    margin=dict(l=20, r=20, t=10, b=60),
)
st.plotly_chart(fig_excess, use_container_width=True)

# =========================================================
# 섹션 9: 리밸런싱 히스토리
# =========================================================
st.markdown('<p class="section-title">리밸런싱 히스토리</p>', unsafe_allow_html=True)

first_period = GROUP_PERIODS.get(invest_groups[0], ("2025-01-02", "2026-01-14"))
last_period_cal = GROUP_PERIODS.get(invest_groups[-1], ("2025-01-02", "2026-01-14"))
min_date = datetime.strptime(first_period[0], "%Y-%m-%d").date()
max_date = datetime.strptime(last_period_cal[1], "%Y-%m-%d").date()
default_date = datetime.strptime(
    GROUP_PERIODS.get(latest_group, (last_period_cal[1],))[0], "%Y-%m-%d"
).date()

picked_date = st.date_input(
    "날짜를 선택하면 해당 기간의 포트폴리오를 확인할 수 있습니다",
    value=default_date, min_value=min_date, max_value=max_date,
)
selected_group = date_to_group(picked_date, invest_groups)
sel_period = GROUP_PERIODS.get(selected_group, ("", ""))
st.caption(f"투자 기간: {sel_period[0]} ~ {sel_period[1]}")

sel_h = holdings[selected_group].copy()

col_tbl, col_pie = st.columns([3, 2])
with col_tbl:
    disp_h = pd.DataFrame({
        "종목명": sel_h["종목명"],
        "비중": (sel_h[w_col] * 100).map("{:.1f}%".format),
        "수익률": (sel_h["return"] * 100).map("{:+.2f}%".format),
        "기여도": (sel_h[contrib_col] * 100).map("{:+.3f}%".format),
        "비고": sel_h["비고"],
    })
    st.dataframe(disp_h, use_container_width=True, hide_index=True)

with col_pie:
    fig_pie = px.pie(
        names=sel_h["종목명"], values=sel_h[w_col], hole=0.4,
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label",
                          textfont_size=10)
    fig_pie.update_layout(
        height=350, margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True, legend=dict(font=dict(size=10)),
    )
    st.plotly_chart(fig_pie, use_container_width=True)
