import pandas as pd
import os

# 1. 대상 엑셀 파일 리스트
excel_files = [
    "2025_상반기_수급강도_랭킹_시총_2000억.xlsx",
    "2025_상반기_수급강도_랭킹_시총_5000억.xlsx",
    "2025_하반기_수급강도_최종랭킹_시총_2천억.xlsx",
    "2025_하반기_수급강도_최종랭킹_시총_5천억.xlsx"
]

_SCRIPT_DIR = os.path.dirname(__file__)
input_dir = os.path.join(_SCRIPT_DIR, "../file/monthly_raw_data")
base_output_dir = os.path.join(_SCRIPT_DIR, "../file/monthly_csv_data")

def split_excel_to_csv_by_folder(file_list):
    print(">>> 엑셀 시트 분리 및 폴더별 저장 시작...")
    
    for file in file_list:
        file_path = os.path.join(input_dir, file)
        
        if not os.path.exists(file_path):
            print(f"파일을 찾을 수 없습니다: {file_path}")
            continue
            
        # 1. 시가총액 키워드 추출 및 폴더 경로 설정
        if "2000" in file or "2천" in file:
            cap_size = "2천억"
        elif "5000" in file or "5천" in file:
            cap_size = "5천억"
        else:
            cap_size = "기타"
            
        # 하위 폴더 경로 생성 (예: ./data/monthly_csv_data/시총2천억)
        target_sub_dir = os.path.join(base_output_dir, f"시총{cap_size}")
        if not os.path.exists(target_sub_dir):
            os.makedirs(target_sub_dir)
            
        # 2. 엑셀 파일 읽기
        excel_dict = pd.read_excel(file_path, sheet_name=None)
        print(f"\n== 파일 처리 중: {file} -> {cap_size} 폴더로 분류 ==")
        
        for sheet_name, df in excel_dict.items():
            clean_sheet_name = sheet_name.strip()
            
            # 3. 파일명 생성: 2025_{시트명}_시총{2/5천억}_수급강도랭킹.csv
            new_csv_name = f"2025_{clean_sheet_name}_시총{cap_size}_수급강도랭킹.csv"
            csv_path = os.path.join(target_sub_dir, new_csv_name)
            
            # 4. CSV 저장
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"   == 저장 완료: {new_csv_name} ==")

# 실행
split_excel_to_csv_by_folder(excel_files)