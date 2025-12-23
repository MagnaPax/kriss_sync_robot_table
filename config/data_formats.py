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
    'X': {'name': 'axis_x',             'type': float},     # X 좌표 (mm)
    'Y': {'name': 'axis_y',             'type': float},     # Y 좌표 (mm)
    'Z': {'name': 'axis_z',             'type': float},     # Z 좌표 (mm)
    'W': {'name': 'yaw',                'type': float},     # Yaw(회전) 각도 (deg)
    'P': {'name': 'pitch',              'type': float},     # Pitch(상하 기울기) 각도 (deg)
    'R': {'name': 'roll',               'type': float},     # Roll(좌우 비틀기) 각도 (deg)
    'M': {'name': 'tool_rotation_rpm',  'type': float},     # 툴 자전 속도 (rpm)
    'N': {'name': 'tool_revolution_rpm','type': float}      # 툴 공전 속도 (rpm)
}


# =============================================================================
# [STORAGE] 매크로 저장/로드용 스키마
# =============================================================================
# 용도: 사용자 정의 매크로(MacroSettingsDialog)를 JSON 파일로 저장하거나 검증할 때 사용
MACRO_SCHEMA: dict[str, type] = {
    'macro_id': str,
    'name': str,        # 사용자 지정 제목 (예: "홈 위치")
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
# [OUTPUT] 서보 모터(Panasonic) 제어용 설정
# =============================================================================
# 용도: 3개의 서보 모터에 대한 축 매핑, 제어 모드, 단위 변환 계수 정의
# 위치: ServoAdapter나 Executor에서 참조하여 명령 생성 시 사용
SERVO_SCHEMA: dict[str, dict] = {
    # -----------------------------------------------------------
    # Axis 1: Tool Revolution (공전)
    # -----------------------------------------------------------
    'tool_revolution_rpm': {
        'axis_index': 1,        # PLC 변수 인덱스 (vel1, pos1...)
        'control_mode': 'velocity', # 제어 방식: 속도(Velocity) vs 위치(Position)
        'scale_factor': 6.0,    # 단위 변환: RPM * 6.0 = deg/s
        'description': 'Tool 공전 모터 (Axis 1)'
    },

    # -----------------------------------------------------------
    # Axis 2: Tool Rotation (자전)
    # -----------------------------------------------------------
    'tool_rotation_rpm': {
        'axis_index': 2,
        'control_mode': 'velocity',
        'scale_factor': 6.0,    # 단위 변환: RPM * 6.0 = deg/s
        'description': 'Tool 자전 모터 (Axis 2)'
    },

    # -----------------------------------------------------------
    # Axis 3: Turntable (턴테이블)
    # -----------------------------------------------------------
    'turntable_deg': {
        'axis_index': 3,
        'control_mode': 'position', # 절대 위치 이동
        'scale_factor': 1.0,    # 단위 변환: deg -> deg (변환 없음)
        'description': '턴테이블 모터 (Axis 3)'
    }
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

# =============================================================================
# [SELECTOR] 실행기(Executor) 판별용 키 집합
# =============================================================================
# 용도: 파일 파싱 후 어떤 실행기(Executor)를 사용할지 결정할 때 사용
# 위치: twincat_commander.py 의 can_execute() 메서드들

# 1. 로봇(FANUC) 제어와 관련된 키
ROBOT_KEYS = {
    'x', 'y', 'z', 'w', 'p', 'r',             # 내부 변수명 (FanucOnly)
    'axis_x', 'axis_y', 'axis_z',             # TXT 스키마 변수명 (Legacy)
    'polar_coord_radius', 'paraboloid_height' # CSV 통합 스키마 변수명 (Integrated)
}

# 2. 서보(Panasonic) 제어와 관련된 키
SERVO_KEYS = {
    'turntable_deg',        # 턴테이블 각도
    'tool_revolution_rpm',  # 툴 공전
    'tool_rotation_rpm',    # 툴 자전
    'polar_coord_theta',    # 통합 제어에서의 턴테이블 각도
    'turntable_feed_rate'   # 턴테이블 속도
}
