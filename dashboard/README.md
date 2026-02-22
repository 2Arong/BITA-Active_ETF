# Ko-ActiveETF 대시보드

우리자산운용 ETF 상품 페이지 스타일의 Streamlit 인터랙티브 대시보드.

## 실행 방법

```bash
cd Ko-ActiveETF
streamlit run dashboard/app.py
```

페이지 접속 시 백테스팅이 자동으로 실행된다. 첫 실행 시 FinanceDataReader API 호출로 1~3분이 소요되며, 이후 동일 세션에서는 캐시(`st.cache_data`, TTL 1시간)가 적용되어 즉시 표시된다.

## 고정 설정

| 항목 | 값 |
|---|---|
| 시그널 유형 | 외국인단독 |
| 비중 방식 | 동일비중 (중복 종목 2배 가중) |
| 가격 기준 | 종가 (Close) |
| 리밸런싱 주기 | 2주 |
| 기준 가격 (NAV 초기값) | 10,000원 |

## NAV (기준 가격) 계산 방식

대시보드에서 표시하는 NAV는 실제 ETF의 순자산가치(Net Asset Value)를 모사한 가상 기준 가격이다.

### 산출 공식

```
NAV_t = NAV_BASE × ∏(1 + r_i),  i = 1, 2, ..., t
```

- **NAV_BASE** = 10,000원 (설정일 초기 기준가)
- **r_i** = i번째 리밸런싱 기간의 포트폴리오 수익률

### 기간 수익률 r_i 산출

각 2주 리밸런싱 기간에 대해:

1. 이전 기간(GN)에서 선정된 종목 리스트와 비중(동일비중, 중복 종목 2배)을 확정
2. 다음 기간(GN+1)의 시작일 종가로 매수, 종료일 종가로 매도하여 종목별 수익률을 산출
3. 종목별 수익률을 비중 가중 합산하여 해당 기간의 포트폴리오 수익률 r_i를 산출

```
r_i = Σ(w_j × r_j),  j = 1, 2, ..., 종목 수
```

- **w_j** = j번째 종목의 비중 (중복 선정 종목은 2배 가중 후 전체 합이 1이 되도록 정규화)
- **r_j** = j번째 종목의 기간 수익률 = (종료일 종가 / 시작일 종가) - 1

### 벤치마크 NAV

KOSPI(`KS11`), KOSPI 200(`KS200`), KoAct 배당성장액티브 ETF(`441800`)도 동일한 방식으로 각 기간의 지수/ETF 수익률을 누적하여 10,000원 기준 NAV를 산출한다.

## 대시보드 구성 (8개 섹션)

| 섹션 | 내용 |
|---|---|
| 상단 헤더 | ETF 이름, NAV, 전 기간 대비 등락, 설정일 이후 총 수익률, 기준일/설정일 |
| 수익률 | 1개월 / 3개월 / 6개월 / 1년 탭별 My ETF vs KOSPI vs KOSPI 200 vs KoAct 메트릭 + 미니 NAV 차트 |
| 기준 가격 및 기초 지수 | 10,000원 정규화 NAV 라인차트 + 벤치마크 3종 |
| 자산 구성 내역 + 종목별 비중 TOP5 | 선정 유형별 (중복/단기/장기) 도넛차트 · 종목 TOP5 도넛차트 + 테이블 |
| 업종별 비중 TOP5 | `fdr.StockListing('KRX-DESC')` 업종 매핑 기반 수평 바차트 + 종목명 포함 테이블 |
| 성과 지표 | 총 수익률, 샤프 비율, MDD, 정보비율(IR), 승률 메트릭 카드 |
| 기간별 초과수익 | KOSPI 대비 초과수익 바차트 (실제 투자 기간 레이블, hovering 시 소수점 4자리) |
| 리밸런싱 히스토리 | 캘린더 날짜 선택으로 해당 기간 보유종목 상세 + 비중 도넛차트 |

## 아키텍처

```
dashboard/app.py
  ├── import: experiment/2w/backtesting_2w.py (run_backtest, 성과 지표 함수)
  ├── import: FinanceDataReader (업종 매핑용 StockListing, 주가/지수 조회)
  └── 데이터: data/file/rebal_2w_csv/외국인단독/g1~g25.csv
```

- `experiment/2w/backtesting_2w.py`의 `run_backtest()`를 `sys.path` 조작으로 import
- 업종 정보는 `fdr.StockListing('KRX-DESC')`에서 런타임 조회 후 24시간 캐싱
- 백테스팅 결과는 `st.cache_data`로 1시간 캐싱

## 의존성

`requirements.txt`에 포함된 패키지 외 추가 필요 없음:

- `streamlit` -- 대시보드 프레임워크
- `plotly` -- 인터랙티브 차트
- `FinanceDataReader` -- 주가 및 업종 데이터 조회
