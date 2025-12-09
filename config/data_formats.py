# config/data_formats.py
"""
데이터 파일 형식 명세 (Schema Definitions)
---------------------------------------
외부 파일(CSV, TXT)과 내부 로직, 그리고 PLC 통신 간의 데이터 구조를 정의합니다.

데이터 흐름:
    1. 파일 로드 (CSV/TXT) -> [CSV_SCHEMA / TXT_SCHEMA]를 사용해 파싱
    2. 파서 -> [DEFAULT_VALUES] (status, result) 주입
    3. Service/Worker -> [FANUC_SCHEMA]를 사용해 PLC 전송용 데이터로 변환

사용법:
    from config.data_formats import TXT_SCHEMA, CSV_SCHEMA
"""

from typing import List, Dict



# =============================================================================
# [INPUT] 외부 파일 파싱용 스키마
# =============================================================================

# --- CSV 파일 형식 (통합 제어용) --- #
# 용도: 로봇 팔과 턴테이블을 동시에 제어하는 시퀀스 파일 (*.csv)
# 특징: 'TwinCATCommander'의 'IntegratedExecutor'에서 사용됨
# 매핑: 파일 헤더(Key) -> 내부 변수명(Name) & 데이터 타입(Type)
CSV_SCHEMA: dict[str, dict] = {
    'PRLINE': {'name': 'id','type': int},                   # 시퀀스 고유 번호 (Key로 사용됨)
    'F': {'name': 'turntable_feed_rate','type': float},     # 턴테이블 회전 속도
    'U': {'name': 'polar_coord_theta',  'type': float},     # 극좌표계 Theta (각도) -> 턴테이블 회전량
    'X': {'name': 'polar_coord_radius', 'type': float},     # 극좌표계 Radius (반지름)
    'Z': {'name': 'paraboloid_height',  'type': float},     # 쌍곡포물면 높이 (Z축)
    'A': {'name': 'untitle',            'type': float},     # (사용 안 함) 더미 데이터
    'B': {'name': 'tool_stroke_rpm',    'type': float},     # 엔드 이펙터(Tool) 스트로크 속도
}

# --- TXT 파일 형식  --- #
# 용도: 구형 시퀀스 파일 (*.txt)
# 특징: 로봇 좌표(X~R) 외에도 턴테이블(T) 및 툴 회전(M, N) 제어가 포함됨
# 주의: 파일에 헤더가 없으므로 '순서'가 매우 중요함 (인덱스 0~9 매핑)
TXT_SCHEMA: dict[str, dict] = {
    'F': {'name': 'feed_rate',          'type': float},     # 이동 속도 (deg/sec) 또는 (mm/sec)
    'T': {'name': 'turntable_deg',      'type': float},     # 턴테이블 각도 (deg)
    'X': {'name': 'x_coord',            'type': float},     # X 좌표 (mm)
    'Y': {'name': 'y_coord',            'type': float},     # Y 좌표 (mm)
    'Z': {'name': 'z_coord',            'type': float},     # Z 좌표 (mm)
    'W': {'name': 'w_angle',            'type': float},     # W 각도 (deg)
    'P': {'name': 'p_angle',            'type': float},     # P 각도 (deg)
    'R': {'name': 'r_angle',            'type': float},     # R 각도 (deg)
    'M': {'name': 'tool_rotation_rpm',  'type': float},     # 툴 자전 속도 (rpm)
    'N': {'name': 'tool_revolution_rpm','type': float}      # 툴 공전 속도 (rpm)
}


# =============================================================================
# [STORAGE] 매크로 저장/로드용 스키마
# =============================================================================
# 용도: 사용자 정의 매크로(MacroSettingsDialog)를 JSON 파일로 저장하거나 검증할 때 사용
MACRO_SCHEMA: dict[str, type] = {
    'macro_id': str,
    'name': str,        # 사용자 지정 설명 (예: "홈 위치")
    'x': float,
    'y': float,
    'z': float,
    'w': float,
    'p': float,
    'r': float
}

# 화면 표시용 레이블 (UI 생성 시 활용 가능)
MACRO_UI_LABELS: Dict[str, str] = {
    'x': 'X (mm)',
    'y': 'Y (mm)',
    'z': 'Z (mm)',
    'w': 'W (deg)',
    'p': 'P (deg)',
    'r': 'R (deg)'
}


# =============================================================================
# [OUTPUT] PLC 통신용
# =============================================================================
# 용도: 내부 데이터를 PLC(TwinCAT/FANUC)가 이해할 수 있는 키로 최종 변환
# 매핑: 내부 변수명(Source) -> PLC 데이터 키(Key)
# 위치: Worker의 _transform_to_fanuc_format 메서드에서 참조함
FANUC_SCHEMA: dict[str, dict] = { 
    'F': {'source': 'feed', 'type': float},
    'X': {'source': 'x',    'type': float},
    'Y': {'source': 'y',    'type': float},
    'Z': {'source': 'z',    'type': float},
    'W': {'source': 'w',    'type': float},
    'P': {'source': 'p',    'type': float},
    'R': {'source': 'r',    'type': float}
}



# =============================================================================
# [INTERNAL] 상태 관리 상수 및 기본값
# =============================================================================
class TaskStatus:
    """작업 진행 상태"""
    UNPROCESSED = 'unprocessed' # 대기 중 (아직 시작 안 함)
    PROCESSING = 'processing'   # 실행 중 (현재 로봇이 이동 중)
    PROCESSED = 'processed'     # 완료됨 (이 줄은 실행 끝남)

class TaskResult:
    """작업 최종 결과"""
    PENDING = 'pending'         # 결과 대기 (아직 모름)
    COMPLETED = 'completed'     # 성공
    FAILED = 'failed'           # 실패 (에러 발생)


# 용도: 파일에는 없지만, 앱 구동을 위해 파서가 강제로 주입해야 하는 기본값들
# 위치: SequenceParser.parse() 메서드에서 사용됨
DEFAULT_VALUES: dict[str, str] = {
    'status': TaskStatus.UNPROCESSED,
    'result': TaskResult.PENDING
}
