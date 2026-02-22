import pandas as pd
import os

# ─────────────────────────────────────────────
# 2주 리밸런싱 엑셀 → CSV 분할
# 상반기/하반기 컬럼명을 통일하여 저장
#
# 통일 컬럼: 티커, 종목명, 강도_단기, 강도_장기, 최종점수, 비고
# ─────────────────────────────────────────────

_SCRIPT_DIR = os.path.dirname(__file__)
INPUT_DIR = os.path.join(_SCRIPT_DIR, "../file/rebal_2w_raw")
OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "../file/rebal_2w_csv")

FILE_MAP = {
    "외국인단독": [
        ("2025_상반기_수급강도_최종랭킹_외국인단독.xlsx", "상반기"),
        ("2025_하반기_수급강도_최종랭킹_그룹별.xlsx", "하반기"),
    ],
    "기관포함": [
        ("2025_상반기_수급강도_최종랭킹_기관포함.xlsx", "상반기"),
        ("2025_하반기_수급강도_최종랭킹_그룹별_기관포함.xlsx", "하반기"),
    ],
}

# 상반기/하반기 컬럼 매핑 → 통일 포맷
COLUMN_RENAMES = {
    "상반기_외국인단독": {
        "종목코드": "티커",
        "최종_수급점수(외국인)": "최종점수",
        "비고(선정사유)": "비고",
    },
    "상반기_기관포함": {
        "종목코드": "티커",
        "최종_수급점수": "최종점수",
        "비고(선정사유)": "비고",
    },
    "하반기": {
        "강도_단기(10d)": "강도_단기",
        "강도_장기(20d)": "강도_장기",
    },
}

KEEP_COLUMNS = ["티커", "종목명", "강도_단기", "강도_장기", "최종점수", "비고"]


def normalize_df(df, half, signal_type):
    """컬럼명을 통일 포맷으로 변환"""
    if half == "상반기":
        rename_map = COLUMN_RENAMES[f"상반기_{signal_type}"]
    else:
        rename_map = COLUMN_RENAMES["하반기"]

    df = df.rename(columns=rename_map)

    available = [c for c in KEEP_COLUMNS if c in df.columns]
    return df[available].copy()


def split_all():
    for signal_type, file_list in FILE_MAP.items():
        out_dir = os.path.join(OUTPUT_DIR, signal_type)
        os.makedirs(out_dir, exist_ok=True)

        for file_name, half in file_list:
            file_path = os.path.join(INPUT_DIR, file_name)

            if not os.path.exists(file_path):
                print(f"[경고] 파일 없음: {file_path}")
                continue

            xl = pd.read_excel(file_path, sheet_name=None)
            print(f"\n== {file_name} ({signal_type}) ==")

            for sheet_name, df in xl.items():
                normalized = normalize_df(df, half, signal_type)
                csv_name = f"{sheet_name.strip().lower()}.csv"
                csv_path = os.path.join(out_dir, csv_name)
                normalized.to_csv(csv_path, index=False, encoding="utf-8-sig")
                print(f"  저장: {csv_name} ({len(normalized)}종목)")

    print(f"\n>> 완료! CSV 저장 위치: {OUTPUT_DIR}/")


if __name__ == "__main__":
    split_all()
