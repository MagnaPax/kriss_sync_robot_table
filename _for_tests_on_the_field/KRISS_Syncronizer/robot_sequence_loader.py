# for_robot_team/robot_sequence_loader.py
"""
로봇팀용 시퀀스 데이터 로더
사용법:
    from robot_sequence_loader import load_robot_sequence
    sequence = load_robot_sequence("path/to/your/file.csv")
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# 내부 모듈을 참조하기 위해 경로 설정
CURRENT_DIR = Path(__file__).parent.absolute()
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

try:
    from parsers.sequence_parser import SequenceParserManager
    from utils.file_handler import load_csv, load_text
except ImportError:
    # 경로 문제 시 직접 추가 시도
    sys.path.append(str(CURRENT_DIR / "parsers"))
    sys.path.append(str(CURRENT_DIR / "utils"))
    from parsers.sequence_parser import SequenceParserManager
    from utils.file_handler import load_csv, load_text

def load_robot_sequence(file_path: str) -> List[Dict[str, Any]]:
    """
    파일(CSV 또는 TXT)을 읽어서 파싱된 시퀀스 데이터를 리턴한다.
    로봇팀은 이 메서드만 호출하면 되며, 리턴된 리스트의 각 항목(Dict)은 아래의 키를 포함한다.

    Returns:
        List[Dict[str, Any]]: 아래 구조를 가진 딕셔너리들의 리스트
        
        [공통 키]
        - 'id' (int): 시퀀스 고유 번호 (CSV의 PRLINE 번호)
        - 'status' (str): 작업 상태 ('unprocessed', 'processing', 'processed')
        - 'result' (str): 작업 결과 ('pending', 'completed', 'failed')

        [데이터 키 - CSV 기준]
        - 'turntable_feed_rate' (float): 턴테이블 이동 속도
        - 'polar_coord_theta' (float): 극좌표계 각도(Theta, deg). 턴테이블 회전량으로 사용됨.
        - 'polar_coord_radius' (float): 극좌표계 반지름(Radius, mm). 로봇의 수평 이동 거리(X).
        - 'paraboloid_height' (float): 쌍곡포물면 높이(Z, mm). 로봇의 수직 높이(Z).
        - 'tool_stroke_rpm' (float): 툴 스트로크(B) 속도
        
        [데이터 키 - TXT 기준]
        - 'feed_rate' (float): 이동 속도
        - 'turntable_deg' (float): 턴테이블 각도 (deg)
        - 'x_coord', 'y_coord', 'z_coord' (float): 로봇 XYZ 좌표 (mm)
        - 'w_angle', 'p_angle', 'r_angle' (float): 로봇 WPR 회전 각도 (deg)
        - 'tool_rpm_rotation' (float): 툴 자전 속도 (rpm)
        - 'tool_rpm_revolution' (float): 툴 공전 속도 (rpm)
    
    Args:
        file_path (str): 읽을 파일의 전체 경로 (예: "sequence_sample.csv")
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
    
    # 1. 파서 매니저 생성 및 적절한 파서 찾기
    manager = SequenceParserManager()
    parser = manager.find_parser(path_obj)
    
    # 2. 파일 형식에 맞춰 데이터 로드
    if path_obj.suffix.lower() == ".csv":
        raw_data = load_csv(path_obj)
    else:
        raw_data = load_text(path_obj)
        
    # 3. 파싱 수행
    # parser.parse()는 Dict[str, Dict] (ID 기준)을 리턴하므로 리스트로 변환
    parsed_map = parser.parse(raw_data)
    
    # 순서 보장을 위해 ID 순서나 꽂힌 순서대로 리스트화
    sequence_list = []
    for key in parsed_map:
        item = parsed_map[key]
        sequence_list.append(item)
        
    return sequence_list

if __name__ == "__main__":
    # 간단한 테스트 코드 (for_robot_team 폴더에서 직접 실행 시)
    test_file = CURRENT_DIR.parent / "_for_tests_on_the_field" / "테스트용데이터" / "sequence_sample.csv"
    if test_file.exists():
        try:
            result = load_robot_sequence(str(test_file))
            print(f"✅ 테스트 성공! 총 {len(result)}건의 데이터를 읽었습니다.")
            for i, row in enumerate(result[:2], 1):
                print(f"Sample {i}: {row}")
        except Exception as e:
            print(f"❌ 에러 발생: {e}")
    else:
        print(f"ℹ️ 테스트 파일을 찾을 수 없어 건너뜁니다. (경로: {test_file})")
