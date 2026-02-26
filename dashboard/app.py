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
import json
import yfinance as yf
import requests
import html
from openai import OpenAI

from backtesting_2w import (
    GROUP_PERIODS, GROUP_KEYS, PRICE_LABEL,
    run_backtest, calc_sharpe, calc_mdd, calc_ir, calc_win_rate,
)

NAV_BASE = 10_000

# ─────────────────────────────────────────────
# 🎨 BITAmin 맞춤형 디자인 테마 (주황색 강조 & 큰 이모티콘)
# ─────────────────────────────────────────────
THEME_ORANGE = "#FF6F00"       # 메인 진한 주황
THEME_LIGHT_ORANGE = "#FFB300" # 밝은 주황 (골드 느낌)
THEME_ACCENT_ORANGE = "#FF8F00" # 중간 주황
THEME_SUB_PURPLE = "#8E24AA"    # 보조 보라 (포인트용)

# 차트 색상 팔레트 (주황색 계열 중심으로 구성)
THEME_COLORS = [
    THEME_ORANGE, THEME_LIGHT_ORANGE,
    "#FF5722", "#FFC107", "#FF9800",
    THEME_SUB_PURPLE, "#F57C00", "#FFD54F"
]

# ─────────────────────────────────────────────
# 페이지 설정 및 CSS 디자인
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="BITActive ETF 대시보드", # 👈 탭 이름 변경
    page_icon="🍊", 
    layout="wide",
)

st.markdown(f"""
<style>
    /* 상단 네비게이션 카드 (주황색 그라데이션 + 큰 오렌지 이모티콘) */
    .nav-card {{
        background: linear-gradient(135deg, {THEME_ORANGE} 0%, {THEME_LIGHT_ORANGE} 100%);
        padding: 2rem 2.5rem; border-radius: 1.2rem; color: white;
        box-shadow: 0 6px 20px rgba(255, 111, 0, 0.4); /* 주황색 그림자 강화 */
        position: relative; 
        overflow: hidden;   
    }}
    /* 큰 오렌지 이모티콘 스타일 (크고 진하게!) */
    .nav-card::after {{
        content: '🍊';
        font-size: 13rem; /* 엄청 크게 키움 */
        position: absolute;
        right: -10px;
        bottom: -40px;
        opacity: 0.45; /* 기존 0.2에서 0.45로 훨씬 진하게 변경 */
        transform: rotate(-15deg);
        z-index: 0;
    }}
    /* 글자들이 오렌지에 가려지지 않게 z-index 설정 */
    .nav-card > * {{
        position: relative;
        z-index: 1;
    }}
    /* BITA 증권 타이틀 스타일 */
    .broker-title {{ 
        font-size: 1.8rem; 
        font-weight: 900; 
        margin: 0 0 1rem 0; 
        color: rgba(255, 255, 255, 0.95); 
        letter-spacing: 1.5px; 
    }}
    .nav-card .etf-name {{ font-size: 1.1rem; opacity: 0.95; margin: 0; font-weight: 600; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); }}
    .nav-card .nav-price {{ font-size: 3.2rem; font-weight: 800; margin: 0.3rem 0 0.5rem 0; text-shadow: 1px 1px 3px rgba(0,0,0,0.2); line-height: 1.1; }}
    .nav-card .nav-change {{ font-size: 1.15rem; margin-top: 0.3rem; font-weight: 700; }}

    /* 섹션 타이틀 (주황색 텍스트 & 강조선) */
    .section-title {{
        font-size: 1.3rem; font-weight: 700;
        color: {THEME_ORANGE};
        border-left: 5px solid {THEME_LIGHT_ORANGE};
        padding-left: 0.8rem;
        margin-top: 2.5rem; margin-bottom: 1rem;
    }}

    /* 숫자 데이터 색상 주황색으로 통일 */
    [data-testid="stMetricValue"], [data-testid="stMetricDelta"] svg {{ color: {THEME_ORANGE} !important; }}
    
    /* 뉴스 제목 링크 색상 */
    .news-link a {{ color: {THEME_ORANGE} !important; text-decoration: none; font-weight: 600; }}
    .news-link a:hover {{ text-decoration: underline; }}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 헬퍼 함수
# ─────────────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def get_sector_map():
    try:
        listing = fdr.StockListing("KRX-DESC")
        listing["Code"] = listing["Code"].astype(str).str.zfill(6)
        return dict(zip(listing["Code"], listing["Sector"]))
    except Exception:
        pass
    return {}

def calc_window_return(series, n):
    if n is None or n >= len(series): return float((1 + series).prod() - 1)
    tail = series.iloc[-n:]
    return float((1 + tail).prod() - 1)

def parse_bigo_type(bigo: str) -> str:
    s = str(bigo)
    if "중복" in s: return "중복선정 (단기+장기)"
    if "단기" in s: return "단기상위"
    return "장기상위"

def fmt_pct(v, sign=True):
    if sign: return f"{v * 100:+.2f}%"
    return f"{v * 100:.2f}%"

def group_to_date_label(g):
    period = GROUP_PERIODS.get(g)
    if not period: return g
    s = period[0][5:]
    e = period[1][5:]
    return f"{s.replace('-', '.')}~{e.replace('-', '.')}"

def date_to_group(d, group_list):
    for g in group_list:
        period = GROUP_PERIODS.get(g)
        if not period: continue
        s = datetime.strptime(period[0], "%Y-%m-%d").date()
        e = datetime.strptime(period[1], "%Y-%m-%d").date()
        if s <= d <= e: return g
    return group_list[-1]

# --- 재무 데이터 수집 함수 ---
import time as _time

@st.cache_data(ttl=86400, show_spinner=False)
def get_financial_summary(ticker_code):
    code = str(ticker_code).zfill(6)
    max_retries = 3
    for suffix in (".KS", ".KQ"):
        for attempt in range(max_retries):
            try:
                stock = yf.Ticker(f"{code}{suffix}")
                info = stock.info
                if info.get('marketCap'):
                    return {
                        "PER": info.get('forwardPE') or info.get('trailingPE') or 0,
                        "PBR": info.get('priceToBook') or 0,
                        "ROE": info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0,
                        "시가총액": (info.get('marketCap') or 0) / 1e12,
                        "배당수익률": (info.get('dividendYield') or 0) * 100,
                        "_error": None,
                    }
                break
            except Exception as e:
                last_err = str(e)
                if "Rate" in last_err or "Too Many" in last_err:
                    _time.sleep(2 ** attempt)
                else:
                    break
    return {"_error": last_err if 'last_err' in dir() else "데이터를 찾을 수 없습니다"}

# --- 네이버 뉴스 데이터 수집 함수 ---
@st.cache_data(ttl=600, show_spinner=False)
def get_naver_news(query, client_id, client_secret, display=5):
    url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display={display}&sort=sim"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.json().get('items', [])
        else:
            return []
    except Exception:
        return []

@st.cache_data(ttl=3600, show_spinner=False)
def analyze_news_with_gpt(stock_name: str, news_titles: list[str],
                          news_descs: list[str], api_key: str) -> list[dict]:
    """ChatGPT API로 뉴스 제목+본문요약의 호재/악재 판단 및 요약을 수행한다."""
    articles = []
    for i, (t, d) in enumerate(zip(news_titles, news_descs)):
        articles.append(f"{i+1}. 제목: {t}\n   내용: {d}")
    articles_text = "\n".join(articles)
    prompt = (
        f"다음은 '{stock_name}' 관련 최신 뉴스 목록입니다. 각 기사의 제목과 본문 요약이 포함되어 있습니다.\n\n"
        f"{articles_text}\n\n"
        "각 뉴스에 대해 아래 JSON 배열 형식으로만 응답해주세요. 다른 텍스트 없이 JSON만 출력하세요.\n"
        '[\n'
        '  {"번호": 1, "판단": "호재" 또는 "악재" 또는 "중립", "요약": "기사 내용을 바탕으로 한 2~3문장 요약"},\n'
        '  ...\n'
        ']\n'
        "판단 기준: 해당 종목의 주가에 긍정적이면 호재, 부정적이면 악재, 판단이 어려우면 중립."
    )
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=1024,
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except Exception as e:
        return [{"_error": str(e)}]


def load_api_key(key_name: str) -> str | None:
    """로컬 api_key.json → Streamlit secrets 순으로 키를 탐색한다."""
    json_path = os.path.join(_DIR, "api_key.json")
    try:
        with open(json_path, encoding="utf-8") as f:
            keys = json.load(f)
        if key_name in keys:
            return keys[key_name]
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    try:
        return st.secrets[key_name]
    except (KeyError, FileNotFoundError):
        return None


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
change_color = "#FFF59D" if nav_change >= 0 else "#E1F5FE"
change_arrow = "▲" if nav_change >= 0 else "▼"

st.markdown(f"""
<div class="nav-card">
    <div class="broker-title">BITA 증권</div> <p class="etf-name">BiTActive ETF — {sig_label} / {strategy_label}</p> <p class="nav-price">{last_nav:,.0f}원</p>
    <p class="nav-change" style="color:{change_color}; background-color: rgba(0,0,0,0.2); padding: 4px 12px; border-radius: 6px; display: inline-block;">
        전 기간 대비 {change_arrow} {abs(nav_change):,.0f}원 ({nav_change_pct:+.2%})
        &nbsp;&nbsp;|&nbsp;&nbsp;설정일 이후 {total_ret:+.2%}
    </p>
    <p style="font-size:0.8rem; opacity:0.85; margin-top:0.8rem;">
        기준일: {last_period[1]} &nbsp;|&nbsp; 설정일: {GROUP_PERIODS[invest_groups[0]][0]}
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("")

# =========================================================
# 섹션 2: 수익률 (탭 버튼)
# =========================================================
st.markdown('<p class="section-title">수익률</p>', unsafe_allow_html=True)

period_config = { "1년": None, "6개월": 13, "3개월": 6, "1개월": 2 }
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
        rc1.metric("BITActive ETF", fmt_pct(ret_my), f"{delta_vs_kospi:+.1f}%p vs KOSPI") # 👈 이름 변경
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
            name="BITActive ETF", line=dict(color=THEME_ORANGE, width=3), marker=dict(size=6), # 👈 이름 변경
        ))
        fig_tab.add_trace(go.Scatter(
            x=tail_dates, y=tail_kospi, mode="lines", name="KOSPI",
            line=dict(color="#9E9E9E", width=1.5, dash="dash"),
        ))
        fig_tab.add_trace(go.Scatter(
            x=tail_dates, y=tail_k200, mode="lines", name="KOSPI 200",
            line=dict(color="#757575", width=1.5, dash="dash"),
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
    name=f"BITActive ETF", # 👈 이름 변경
    line=dict(color=THEME_ORANGE, width=3), marker=dict(size=6),
    hovertemplate="%{x}<br>%{y:,.0f}원<extra></extra>",
))
fig_nav.add_trace(go.Scatter(
    x=x_dates, y=nav_kospi, mode="lines", name="KOSPI",
    line=dict(color="#9E9E9E", width=1.5, dash="dash"),
    hovertemplate="%{x}<br>%{y:,.0f}원<extra></extra>",
))
fig_nav.add_trace(go.Scatter(
    x=x_dates, y=nav_k200, mode="lines", name="KOSPI 200",
    line=dict(color="#757575", width=1.5, dash="dash"),
    hovertemplate="%{x}<br>%{y:,.0f}원<extra></extra>",
))
fig_nav.add_trace(go.Scatter(
    x=x_dates, y=nav_koact, mode="lines", name="KoAct 배당성장",
    line=dict(color=THEME_SUB_PURPLE, width=2, dash="dashdot"),
    hovertemplate="%{x}<br>%{y:,.0f}원<extra></extra>",
))
fig_nav.add_hline(y=NAV_BASE, line_dash="dot", line_color="gray", annotation_text=f"기준가 {NAV_BASE:,}원")
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

with col_comp:
    st.markdown('<p class="section-title">자산 구성 내역</p>', unsafe_allow_html=True)
    st.caption(f"기준 기간: {last_period[0]} ~ {last_period[1]}")

    h = latest_holdings.copy()
    h["선정유형"] = h["비고"].apply(parse_bigo_type)
    h["비중"] = h[w_col]
    type_weights = h.groupby("선정유형")["비중"].sum().sort_values(ascending=False)

    fig_comp = px.pie(
        names=type_weights.index, values=type_weights.values, hole=0.45,
        color_discrete_sequence=THEME_COLORS,
    )
    fig_comp.update_traces(textposition="inside", textinfo="percent+label", textfont_size=12, marker=dict(line=dict(color='#FFFFFF', width=2)))
    fig_comp.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    st.plotly_chart(fig_comp, use_container_width=True)

    comp_df = pd.DataFrame({ "선정유형": type_weights.index, "비중": type_weights.values })
    comp_df["비중"] = comp_df["비중"].map(lambda v: f"{v * 100:.1f}%")
    st.dataframe(comp_df, width="stretch", hide_index=True)

with col_stock:
    st.markdown('<p class="section-title">주식 종목별 비중 TOP5</p>', unsafe_allow_html=True)
    st.caption(f"기준 기간: {last_period[0]} ~ {last_period[1]}")

    top5_stocks = h.nlargest(5, w_col)[["종목명", w_col]].copy()
    top5_stocks["비중(%)"] = top5_stocks[w_col] * 100

    fig_stock = px.pie(
        names=top5_stocks["종목명"], values=top5_stocks["비중(%)"], hole=0.45,
        color_discrete_sequence=THEME_COLORS,
    )
    fig_stock.update_traces(
        textposition="inside", textinfo="percent+label", textfont_size=12,
        hovertemplate="%{label}<br>비중: %{value:.1f}%<extra></extra>",
        marker=dict(line=dict(color='#FFFFFF', width=2))
    )
    fig_stock.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    st.plotly_chart(fig_stock, use_container_width=True)

    disp_stock = top5_stocks[["종목명"]].copy()
    disp_stock["비중"] = top5_stocks[w_col].map(lambda v: f"{v * 100:.1f}%")
    st.dataframe(disp_stock, width="stretch", hide_index=True)

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
        x=sector_weights.values[::-1], y=sector_weights.index[::-1], orientation="h",
        marker_color=THEME_LIGHT_ORANGE,
        text=[f"{v * 100:.1f}%" for v in sector_weights.values[::-1]], textposition="auto",
    ))
    fig_sector.update_layout(
        height=300, xaxis_title="비중", xaxis_tickformat=".0%",
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig_sector, use_container_width=True)

with col_sec_tbl:
    sec_df = pd.DataFrame({
        "업종": sector_weights.index, "비중": sector_weights.values,
        "종목": [sector_stocks[s] for s in sector_weights.index],
    })
    sec_df["비중"] = sec_df["비중"].map(lambda v: f"{v * 100:.1f}%")
    st.dataframe(sec_df, width="stretch", hide_index=True)

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
c1.metric("총 수익률", fmt_pct(total_ret, sign=False), f"{(total_ret - calc_window_return(b_ret, None)) * 100:+.1f}%p vs KOSPI")
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
    marker_color=[(THEME_ORANGE if v >= 0 else THEME_SUB_PURPLE) for v in excess],
    hovertemplate="%{x}<br>초과수익: %{y:+.4f}%p<extra></extra>",
))
fig_excess.add_hline(y=0, line_color="black", line_width=1)
fig_excess.update_layout(
    height=250, yaxis_title="초과수익 (%p vs KOSPI)", xaxis=dict(tickangle=-45),
    margin=dict(l=20, r=20, t=10, b=60),
)
st.plotly_chart(fig_excess, use_container_width=True)

# =========================================================
# 섹션 9: 리밸런싱 히스토리 및 기업 분석 
# =========================================================
st.markdown('<p class="section-title">리밸런싱 히스토리 및 기업 분석</p>', unsafe_allow_html=True)

first_period = GROUP_PERIODS.get(invest_groups[0], ("2025-01-02", "2026-01-14"))
last_period_cal = GROUP_PERIODS.get(invest_groups[-1], ("2025-01-02", "2026-01-14"))
min_date = datetime.strptime(first_period[0], "%Y-%m-%d").date()
max_date = datetime.strptime(last_period_cal[1], "%Y-%m-%d").date()
default_date = datetime.strptime(GROUP_PERIODS.get(latest_group, (last_period_cal[1],))[0], "%Y-%m-%d").date()

picked_date = st.date_input(
    "날짜를 선택하면 해당 기간의 포트폴리오와 상세 재무 정보를 확인할 수 있습니다",
    value=default_date, min_value=min_date, max_value=max_date,
)
selected_group = date_to_group(picked_date, invest_groups)
sel_period = GROUP_PERIODS.get(selected_group, ("", ""))
st.caption(f"투자 기간: {sel_period[0]} ~ {sel_period[1]}")

sel_h = holdings[selected_group].copy()

col_tbl, col_pie, col_fin = st.columns([2.5, 1.5, 2])

with col_tbl:
    st.markdown(f"**<span style='color:{THEME_ORANGE}'>📋 종목별 성과</span>**", unsafe_allow_html=True)
    disp_h = pd.DataFrame({
        "종목명": sel_h["종목명"],
        "비중": (sel_h[w_col] * 100).map("{:.1f}%".format),
        "수익률": (sel_h["return"] * 100).map("{:+.2f}%".format),
        "기여도": (sel_h[contrib_col] * 100).map("{:+.3f}%".format),
    })
    st.dataframe(disp_h, width="stretch", hide_index=True, height=350)

with col_pie:
    st.markdown(f"**<span style='color:{THEME_ORANGE}'>🍩 포트폴리오 비중</span>**", unsafe_allow_html=True)
    fig_pie = px.pie(
        sel_h, names="종목명", values=w_col, hole=0.4,
        color_discrete_sequence=THEME_COLORS
    )
    fig_pie.update_traces(marker=dict(line=dict(color='#FFFFFF', width=2)))
    fig_pie.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
    st.plotly_chart(fig_pie, use_container_width=True)

with col_fin:
    st.markdown(f"**<span style='color:{THEME_ORANGE}'>💰 기업 재무 상태 요약</span>**", unsafe_allow_html=True)
    selected_stock = st.selectbox("분석할 종목 선택", sel_h["종목명"].unique())
    
    if "티커" in sel_h.columns: ticker_col = "티커"
    elif "Code" in sel_h.columns: ticker_col = "Code"
    else: ticker_col = "종목코드"
        
    ticker = sel_h[sel_h["종목명"] == selected_stock][ticker_col].iloc[0]
    
    with st.spinner(f'{selected_stock} 재무 데이터 분석 중...'):
        fin = get_financial_summary(ticker)
        if fin.get("_error"):
            st.error(f"재무 정보를 불러올 수 없습니다.\n\n`{ticker}` → {fin['_error']}")
        else:
            m1, m2 = st.columns(2)
            m1.metric("시가총액", f"{fin['시가총액']:.1f}조")
            m2.metric("배당수익률", f"{fin['배당수익률']:.1f}%")

            m3, m4 = st.columns(2)
            m3.metric("PER", f"{fin['PER']:.1f}배" if fin['PER'] > 0 else "N/A")
            m4.metric("PBR", f"{fin['PBR']:.1f}배" if fin['PBR'] > 0 else "N/A")

            st.write(f"**ROE (자기자본이익률): {fin['ROE']:.1f}%**")
            st.markdown(f"<style>.stProgress > div > div > div > div {{ background-color: {THEME_ORANGE} !important; }}</style>", unsafe_allow_html=True)
            st.progress(min(max(fin['ROE']/30, 0.0), 1.0))

# =========================================================
# 섹션 10: 뉴스 + AI 분석 (좌우 배치)
# =========================================================
st.markdown("---")

NAVER_CLIENT_ID = load_api_key("naver_client_id")
NAVER_CLIENT_SECRET = load_api_key("naver_client_secret")
OPENAI_KEY = load_api_key("secret_key")

clean_titles = []
clean_links = []
clean_descs = []

if NAVER_CLIENT_ID and NAVER_CLIENT_SECRET:
    with st.spinner('최신 뉴스 검색 중...'):
        news_items = get_naver_news(selected_stock, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, display=5)
        if news_items:
            for item in news_items:
                t = html.unescape(item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"'))
                d = html.unescape(item.get('description', '').replace('<b>', '').replace('</b>', '').replace('&quot;', '"'))
                clean_titles.append(t)
                clean_links.append(item['link'])
                clean_descs.append(d)

analysis = []
if clean_titles and OPENAI_KEY:
    with st.spinner("ChatGPT가 뉴스를 분석하고 있습니다..."):
        analysis = analyze_news_with_gpt(selected_stock, clean_titles, clean_descs, OPENAI_KEY)
    if analysis and analysis[0].get("_error"):
        analysis = []

col_news, col_ai = st.columns(2)

with col_news:
    st.markdown(f"""<h4 style='color: {THEME_ORANGE};'>📰 {selected_stock} 실시간 관련 이슈</h4>""",
                unsafe_allow_html=True)
    st.caption(f"최근 5건의 뉴스 제목입니다. 추가적인 정보는 뉴스 링크를 클릭하여 확인할 수 있습니다.")
    if clean_titles:
        for t, link in zip(clean_titles, clean_links):
            st.markdown(f"- [{t}]({link})")
    elif NAVER_CLIENT_ID:
        st.info("검색된 관련 뉴스가 없습니다.")
    else:
        st.warning("네이버 API 키가 설정되지 않았습니다.")

with col_ai:
    st.markdown(f"""<h4 style='color: {THEME_ORANGE};'>🤖 AI의 {selected_stock} 뉴스 분석</h4>""",
                unsafe_allow_html=True)
    if analysis:
        BADGE = {"호재": "🟢", "악재": "🔴", "중립": "🟡"}
        for item in analysis:
            badge = BADGE.get(item.get("판단", "중립"), "🟡")
            idx = item.get("번호", 0) - 1
            title = clean_titles[idx] if 0 <= idx < len(clean_titles) else f"기사 {idx+1}"
            summary = item.get("요약", "")
            st.markdown(f"{badge} **{item.get('판단', '중립')}** — {title}")
            st.markdown(f"> {summary}")
        st.caption("GPT 기반 분석이며, 투자 판단의 근거로 사용하기에 적합하지 않습니다.")
    elif not OPENAI_KEY:
        st.info("OpenAI API 키가 설정되지 않아 분석을 건너뜁니다.")
    elif not clean_titles:
        st.info("분석할 뉴스가 없습니다.")
    else:
        st.error("뉴스 분석에 실패했습니다.")