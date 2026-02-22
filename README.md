# Ko-ActiveETF

외국인/기관 순매수 데이터 기반 **수급 강도 지표**를 활용한 한국형 액티브 ETF 종목 선정 및 백테스팅 시스템.

## 프로젝트 개요

한국 주식시장에서 외국인·기관의 순매수 패턴이 단기 주가 흐름의 선행지표가 될 수 있다는 가설을 검증한다. 수급 강도 지표를 기반으로 종목을 선정하고 정기적으로 리밸런싱하는 규칙 기반 액티브 ETF 모델을 구성·백테스팅한다.

## 종목 선정 로직

1. **유니버스 구성** — 기관 순매수 상위 100개 & 외국인 순매수 상위 100개에서 겹치는 종목 추출
2. **필터링** — 시가총액 5,000억 원 이상 + 60일 평균 거래대금 100억 원 이상
3. **수급 강도 지표** — `누적 외국인(+기관) 순매수 금액 / 유동 시가총액` 기준 내림차순 정렬
   - 유동 시가총액 = 시가총액 × 유동비율(0.5)
4. **종목 선정** — 최근 단기(10일)·장기(20일) 수급 강도 상위 각 10종목 → 합산 최대 16종목 (중복 시 가중치 2배)
5. **투자** — 선정 기간의 다음 기간에 투자 실행

## 실험 설계

| 축 | 변수 |
|---|---|
| 리밸런싱 주기 | 월별 (`1m`) / 2주 (`2w`) |
| 시그널 유형 | 외국인단독 / 기관포함 (외국인+기관) |
| 비중 방식 | 동일비중 (중복 2배) / 점수비중 (최종점수 정규화) |
| 가격 기준 | 종가(Close) / 시가(Open) / VWAP |
| 벤치마크 | KOSPI 종합, KOSPI 200, KoAct 배당성장액티브 ETF |

## 디렉토리 구조

```
Ko-ActiveETF/
├── README.md
├── .gitignore
│
├── data/
│   ├── code/                           # 데이터 전처리 스크립트
│   │   ├── data_split.py               #   월별 Excel → CSV 분할
│   │   └── data_split_2w.py            #   2주 Excel → CSV 분할
│   └── file/
│       ├── monthly_raw_data/           # 월별 원본 Excel
│       ├── monthly_csv_data/           # 월별 CSV (시총2천억 / 시총5천억)
│       ├── rebal_2w_raw/               # 2주 원본 Excel
│       └── rebal_2w_csv/               # 2주 CSV (외국인단독 / 기관포함)
│
├── experiment/
│   ├── 1m/                             # 월별 리밸런싱 실험
│   │   ├── backtesting.py              #   동일비중 백테스팅
│   │   ├── backtesting_score_weighted.py #  동일비중 vs 점수비중 비교
│   │   ├── inspector.py                #   기간별 종목 상세 검증
│   │   ├── inspector_score_weighted.py #   두 비중방식 종목 검증
│   │   └── result/                     #   결과 그래프
│   └── 2w/                             # 2주 리밸런싱 실험
│       ├── backtesting_2w.py           #   메인 백테스팅 (동일/점수 비중)
│       ├── inspector_2w.py             #   기간별 종목 상세 검증
│       └── result/                     #   결과 그래프
│
└── dashboard/                          # Streamlit 대시보드 (예정)
```

## 성과 지표

| 지표 | 설명 |
|---|---|
| 총 수익률 | 전체 기간 누적 수익률 |
| 샤프 비율 | (평균 수익률 − 무위험수익률) / 변동성, 연환산 |
| MDD | 최대 낙폭 (Maximum Drawdown) |
| 정보 비율 (IR) | 초과수익률 / 추적오차, 연환산 |
| 승률 | 벤치마크(KOSPI) 대비 양의 초과수익 기간 비율 |

## 사용법

### 환경 설정

```bash
pip install pandas numpy FinanceDataReader matplotlib openpyxl
```

### 2주 리밸런싱 백테스팅

```bash
# 외국인단독 시그널, 종가 기준
python experiment/2w/backtesting_2w.py --signal 외국인단독 --price close

# 기관포함 시그널, VWAP 기준
python experiment/2w/backtesting_2w.py --signal 기관포함 --price vwap
```

### 월별 리밸런싱 백테스팅

```bash
python experiment/1m/backtesting.py --cap 5천억 --method close
python experiment/1m/backtesting_score_weighted.py --cap 5천억 --method close
```

### 종목 상세 검증

```bash
# 2주 리밸런싱 - 특정 그룹
python experiment/2w/inspector_2w.py --signal 외국인단독 --price close

# 월별 리밸런싱
python experiment/1m/inspector.py --cap 5천억 --price close
```

### 데이터 전처리 (Excel → CSV)

```bash
python data/code/data_split.py       # 월별
python data/code/data_split_2w.py    # 2주
```

## 데이터 소스

- **주가 데이터**: [FinanceDataReader](https://github.com/financedata-org/FinanceDataReader) (Naver/Yahoo Finance 기반)
- **종목 선정 데이터**: 직접 산출한 수급 강도 랭킹 (Excel/CSV)
- **벤치마크**: KOSPI(`KS11`), KOSPI 200(`KS200`), KoAct 배당성장액티브 ETF(`441800`)

## 기술 스택

- Python 3.12
- pandas, numpy — 데이터 처리
- FinanceDataReader — 주가 조회
- matplotlib — 결과 시각화
- Streamlit + Plotly — 인터랙티브 대시보드 (예정)
