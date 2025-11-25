# sequence_parser.py

"""
시퀀스 데이터용 파서


사용법:

        from .parsers.sequence_parser import SequenceParserManager

        # 시퀀스 파서 매니저 객체 생성
        self.parser_manager = SequenceParserManager()

        # 파일 경로에 맞는 파서 객체를 찾기
        parser = self.parser_manager.find_parser(self.file_path)

        # 파일 읽기(file_handler 유틸리티 사용)
        raw_text = load_XXX(self.file_path)

        # 찾아낸 파서로 데이터를 파싱한다.
        parsed_data = parser.parse(raw_text)
"""

from pathlib import Path
from typing import Any, Dict, List
from .base_parser import BaseParser


# 타입 힌트를 위한 별칭 정의
CoordinateDict = Dict[str, float]
SequenceDict = Dict[str, CoordinateDict]



class SequenceTxtParser(BaseParser):

    def can_parse(self, path: Path) -> bool:
        """텍스트 파일인지 확인"""
        return path.suffix.lower() == ".txt"

    def parse(self, data: str | List[str]) -> SequenceDict:
        """
        FANUC 좌표 TXT 파일의 raw 문자열 리스트를 의미있는 딕셔너리 시퀀스로 파싱합니다.

        인자:
            data (List[str]): 각 줄이 '값 값 값...' 형태인 문자열 리스트 (공백 분리)
            
        반환:
            Dict[str, Dict[str, float]]: {'1': {'feed': 10.0, 'x_coord': 95.899, ...}, ...}
        """

        # 입력 데이터 타입에 따른 전처리
        # 들어온 데이터가 통 문자열(str)이라면 줄 단위로 나눈다
        if isinstance(data, str):
            lines = data.strip().splitlines()
        else:
            lines = data

        # 텍스트 파일의 고정된 인덱스 순서 정의
        # 원본 순서: F, T, X, Y, Z, W, P, R, M, N
        FIELD_NAMES = [
            'feed',             # 1번째 값: F (Feed)
            'turntable_deg',    # 2번째 값: T (Turntable 각도)
            'x_coord',          # 3번째 값: X (X 좌표)
            'y_coord',          # 4번째 값: Y (Y 좌표)
            'z_coord',          # 5번째 값: Z (Z 좌표)
            'w_angle',          # 6번째 값: W (W 각도)
            'p_angle',          # 7번째 값: P (P 각도)
            'r_angle',          # 8번째 값: R (R 각도)
            'tool_rpm_rotation',# 9번째 값: M (툴의 자전 RPM)
            'tool_rpm_revolution'# 10번째 값: N (툴의 공전 RPM)
        ]
        
        parsed_data: SequenceDict = {}
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            values = line.split()
            coords: CoordinateDict = {}
            
            # 값을 float으로 변환하여 순서대로 매핑
            for name, value_str in zip(FIELD_NAMES, values):
                coords[name] = float(value_str)
            
            # 딕셔너리 삽입 순서는 FIELD_NAMES와 동일하며, 키는 할당된 값과 일치합니다.
            parsed_data[str(i)] = coords
                
        return parsed_data



class SequenceCsvParser(BaseParser):

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() == ".csv"

    def parse(self, data: List[List[str]]) -> SequenceDict:
        """
        FANUC 좌표 CSV 파일의 raw 리스트를 의미있는 딕셔너리 시퀀스로 파싱합니다.
        (에러 처리는 제외)

        CSV 데이터는 이미 List[List[str]] 형태로 로드되었다고 가정하며,
        내부 데이터는 ['키', '값', '키', '값', ...] 형태로 나열되어 있습니다.
        
        인자:
            data (List[List[str]]): CSV 로더에서 반환된 형태
            
        반환:
            Dict[str, Dict[str, float]]: {'1': {'feed_rate': 10.0, 'radius_r': 5.0, ...}, ...}
        """
        
        # CSV 키와 최종 딕셔너리 이름의 매핑 정의
        KEY_MAPPING = {
            'F': 'feed_rate',            # 초당 회전속도 (feed rate)
            'U': 'polar_coord_θ',        # 각도 (극좌표계의 θ)
            'X': 'polar_coord_radius',   # 반지름 (극좌표계의 r)
            'Z': 'paraboloid_height',    # 파라볼로이드 높이
            'B': 'tool_stroke_rpm',      # 툴 스트로크 속도 (rpm)
        }

        parsed_data: SequenceDict = {}

        for row_list in data:
            if not row_list:
                continue
                
            temp_dict: CoordinateDict = {}
            sequence_number: str = ""
            
            # 키(PRLINE, F, U, X, Z, A, B)와 값(1, 10, 0, 5, ...)이 번갈아 나옴
            for i in range(0, len(row_list), 2):
                if i + 1 >= len(row_list):
                    break
                    
                key = row_list[i].strip()
                value_str = row_list[i+1].strip()
                
                if key == 'PRLINE':
                    sequence_number = value_str
                
                elif key in KEY_MAPPING:
                    new_key = KEY_MAPPING[key]
                    temp_dict[new_key] = float(value_str)
                
                # 'A' 키와 그 값은 KEY_MAPPING에 없으므로 무시됨
            
            if sequence_number:
                parsed_data[sequence_number] = temp_dict
                
        return parsed_data



class SequenceParserManager:

    def __init__(self):
        self.parsers = [
            SequenceTxtParser(),
            SequenceCsvParser(),
        ]

    def find_parser(self, path: Path) -> BaseParser:
        for parser in self.parsers:
            if parser.can_parse(path):
                return parser
        raise ValueError(f"지원하지 않는 파일 형식: {path.suffix}")
