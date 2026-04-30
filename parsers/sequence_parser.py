# parsers/sequence_parser.py

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
from typing import Dict, List, Union
from .base_parser import BaseParser
from config.data_formats import CSV_SCHEMA, DEFAULT_VALUES


# 타입 힌트를 위한 별칭 정의
CoordinateDict = Dict[str, Union[float, str]]
SequenceDict = Dict[str, CoordinateDict]


class SequenceTxtParser(BaseParser):

    def can_parse(self, path: Path) -> bool:
        """텍스트 파일인지 확인"""
        return path.suffix.lower() == ".txt"

    def parse(self, data: str | List[str]) -> SequenceDict:
        """
        FANUC 좌표 TXT 파일의 raw 문자열 리스트를 의미있는 딕셔너리 시퀀스로 파싱

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
            
            # 딕셔너리 삽입 순서는 FIELD_NAMES와 동일하며, 키는 할당된 값과 일치한다
            parsed_data[str(i)] = coords
                
        return parsed_data


class SequenceCsvParser(BaseParser):

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() == ".csv"

    def parse(self, data: List[List[str]]) -> SequenceDict:
        """
        raw 리스트를 CSV_SCHEMA에 맞춰 파싱
        
        인자:
            data: [['PRLINE', '1', 'F', '10', ...], ...] 형태의 리스트
            
        반환:
            {'1': {'turntable_feed_rate': 10.0, ...}, ...}
        """
        parsed_data: SequenceDict = {}

        for row_index, row_list in enumerate(data):
            if not row_list:
                continue
                
            temp_dict: CoordinateDict = {}
            sequence_id: str = ""
            
            # 키-값 쌍으로 순회 (Step 2)
            # 예: row_list[0]='PRLINE', row_list[1]='1', row_list[2]='F', row_list[3]='10' ...
            for i in range(0, len(row_list), 2):
                if i + 1 >= len(row_list):
                    break
                    
                key = row_list[i].strip()
                value_str = row_list[i+1].strip()
                
                # 스키마에 정의된 키인지 확인
                if key in CSV_SCHEMA:
                    schema_info = CSV_SCHEMA[key]
                    field_name = schema_info['name']
                    data_type = schema_info['type']

                    # 의미 없는 칼럼 A는 무시
                    if field_name == 'unused_data_a': 
                        continue

                    if field_name == 'id':
                        sequence_id = value_str # 정수로 변환하지 않고 문자열 키로 유지
                        temp_dict['id'] = int(value_str)

                    else:
                        # 나머지 데이터 처리
                        try:
                            temp_dict[field_name] = data_type(value_str)

                        except ValueError as e:
                            # 변환 실패 시 에러 발생 (어떤 값이 문제인지 알려줌)
                            raise ValueError(
                                f"CSV 파싱 오류 ({row_index+1} 번째 줄) "
                                f"키 '{key}'의 값 '{value_str}'을(를) {data_type.__name__} 타입으로 변환할 수 없습니다."
                            ) from e

            # 작업 진행 상태 확인을 위한 기본값 추가
            temp_dict.update(DEFAULT_VALUES)

            # 유효한 ID가 있으면 결과에 추가
            if sequence_id:
                parsed_data[sequence_id] = temp_dict    # <--- 순서대로 꽂힘!

        return parsed_data


class StandardHeaderCsvParser(BaseParser):
    """
    일반적인 헤더 기반 CSV 파서
        csv 파일의 첫 줄에 헤더가 있는 경우
    """

    def can_parse(self, path: Path) -> bool:
        # 이 클래스는 직접 SequenceParserManager에서 명시적으로 호출됨
        return path.suffix.lower() == ".csv"

    def parse(self, data: List[List[str]]) -> SequenceDict:
        """
        헤더 기반 리스트를 딕셔너리로 파싱
        """
        if not data:
            return {}

        headers = [h.strip() for h in data[0]]
        parsed_data: SequenceDict = {}

        # 2번째 줄(인덱스 1)부터 데이터 처리
        for row_index, row_list in enumerate(data[1:], start=1):
            if not row_list:
                continue

            temp_dict: CoordinateDict = {}
            sequence_id: str = ""

            for i, header in enumerate(headers):
                if i >= len(row_list):
                    break
                
                value_str = row_list[i].strip()
                
                # 'id' 컬럼 처리
                if header.lower() == 'id':
                    sequence_id = value_str
                    temp_dict['id'] = int(value_str)
                else:
                    # 나머지 숫자 데이터 처리
                    try:
                        # 숫자인 경우 float으로 변환, 아니면 문자열 그대로 유지
                        try:
                            temp_dict[header] = float(value_str)
                        except ValueError:
                            temp_dict[header] = value_str
                    except Exception:
                        continue

            # 기본값 주입
            temp_dict.update(DEFAULT_VALUES)

            # ID가 없으면 인덱스를 ID로 사용
            if not sequence_id:
                sequence_id = str(row_index)
                temp_dict['id'] = row_index

            parsed_data[sequence_id] = temp_dict

        return parsed_data


class SequenceParserManager:

    def __init__(self):
        self.parsers = [
            SequenceTxtParser(),
            SequenceCsvParser(),
        ]

    def find_parser(self, path: Path) -> BaseParser:
        suffix = path.suffix.lower()
        
        if suffix == ".txt":
            return SequenceTxtParser()
            
        if suffix == ".csv":
            # CSV인 경우 파일의 첫 줄을 확인하여 형식을 결정
            try:
                from utils.file_handler import load_csv
                raw_data = load_csv(path)
                
                if not raw_data:
                    return SequenceCsvParser() # 빈 파일이면 기본 파서 반환

                first_row = raw_data[0]
                # 첫 줄의 첫 칸이 'PRLINE'이면 기존 "키-값" 형식
                if first_row and first_row[0].strip().upper() == "PRLINE":
                    return SequenceCsvParser()
                else:
                    # 그렇지 않으면 일반 헤더 기반 형식
                    return StandardHeaderCsvParser()
                    
            except Exception:
                # 확인 실패 시 기본 파서 반환
                return SequenceCsvParser()

        raise ValueError(f"지원하지 않는 파일 형식: {suffix}")
