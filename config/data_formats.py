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

from typing import Dict, Any

# =============================================================================
# [CONSTANTS] 데이터 키 상수 정의 (최상단 배치로 NameError 방지 및 Magic String 제거)
# =============================================================================

# 1. 공통 및 메타데이터 키
KEY_ID              = 'id'
KEY_NAME            = 'name'
KEY_MACRO_ID        = 'macro_id'
KEY_ROBOT_FEED_RATE = 'f'
KEY_STATUS          = 'status'
KEY_RESULT          = 'result'

# 2. 로봇(FANUC) 내부 좌표 키 (Internal Property Names)
KEY_ROBOT_X = 'x'
KEY_ROBOT_Y = 'y'
KEY_ROBOT_Z = 'z'
KEY_ROBOT_W = 'w'
KEY_ROBOT_P = 'p'
KEY_ROBOT_R = 'r'

# 3. 서보 모터(Panasonic) 및 턴테이블 키
KEY_TOOL_REV_RPM        = 'tool_revolution_rpm'    # 공전
KEY_TOOL_ROT_RPM        = 'tool_rotation_rpm'      # 자전
KEY_TURNTABLE_DEG       = 'turntable_deg'          # 턴테이블 각도
KEY_TURNTABLE_FEED_RATE = 'turntable_feed_rate'    # 턴테이블 속도
KEY_POLAR_THETA         = 'polar_coord_theta'      # 극좌표 각도 (턴테이블 연동) - Legacy support

# 4. 특수 목적 키 (CSV/Legacy 통합용)
KEY_POLAR_RADIUS    = 'polar_coord_radius'
KEY_PARA_HEIGHT     = 'paraboloid_height'
KEY_TOOL_STROKE     = 'tool_stroke_rpm'
KEY_LEGACY_X        = 'axis_x'
KEY_LEGACY_Y        = 'axis_y'
KEY_LEGACY_Z        = 'axis_z'


# =============================================================================
# [INPUT] 외부 파일 파싱용 스키마
# =============================================================================

# --- CSV 파일 형식 (통합 제어용) --- #
# 용도: 로봇 팔과 턴테이블을 동시에 제어하는 시퀀스 파일 (*.csv)
# 특징: 'TwinCATCommander'의 'IntegratedExecutor'에서 사용됨
# 매핑: 파일 헤더(Key) -> 내부 변수명(Name) & 데이터 타입(Type)
CSV_SCHEMA: Dict[str, Dict[str, Any]] = {
    'PRLINE': {'name': KEY_ID,                  'type': int},      # 시퀀스 고유 번호
    'F':      {'name': KEY_TURNTABLE_FEED_RATE, 'type': float},    # 턴테이블 회전 속도
    'U':      {'name': KEY_TURNTABLE_DEG,       'type': float},    # 턴테이블 각도 (극좌표계의 θ - deg/sec)
    'X':      {'name': KEY_ROBOT_X,             'type': float},    # 로봇 X축 (극좌표계의 r)
    'Z':      {'name': KEY_ROBOT_Z,             'type': float},    # 로봇 Z축 (파라볼로이드 높이)
    'A':      {'name': 'unused_data_a',         'type': float},    # 무시 (의미 없는 칼럼)
    'B':      {'name': KEY_TOOL_REV_RPM,        'type': float},    # 툴 공전 (툴 스트로크 속도 - rpm)
    'C':      {'name': KEY_TOOL_ROT_RPM,        'type': float},    # 툴 자전
}

# --- TXT 파일 형식  --- #
# 용도: 구형 시퀀스 파일 (*.txt)
# 특징: 로봇 좌표(X~R) 외에도 턴테이블(T) 및 툴 회전(M, N) 제어가 포함됨
# 주의: 파일에 헤더가 없으므로 '순서'가 매우 중요함 (인덱스 0~9 매핑)
TXT_SCHEMA: Dict[str, Dict[str, Any]] = {
    'F': {'name': 'feed_rate',           'type': float},        # 이동 속도
    'T': {'name': KEY_TURNTABLE_DEG,     'type': float},        # 턴테이블 각도
    'X': {'name': KEY_LEGACY_X,          'type': float},        # X 좌표
    'Y': {'name': KEY_LEGACY_Y,          'type': float},        # Y 좌표
    'Z': {'name': KEY_LEGACY_Z,          'type': float},        # Z 좌표
    'W': {'name': 'yaw',                 'type': float},        # Yaw
    'P': {'name': 'pitch',               'type': float},        # Pitch
    'R': {'name': 'roll',                'type': float},        # Roll
    'M': {'name': KEY_TOOL_ROT_RPM,      'type': float},        # 툴 자전
    'N': {'name': KEY_TOOL_REV_RPM,      'type': float}         # 툴 공전
}


# =============================================================================
# [STORAGE] 매크로 저장/로드용 스키마
# =============================================================================
# 용도: 사용자 정의 매크로(MacroSettingsDialog)를 JSON 파일로 저장하거나 검증할 때 사용
MACRO_SCHEMA: dict[str, type] = {
    KEY_MACRO_ID: str,
    KEY_NAME:     str,          # 사용자 지정 제목 (예: "홈 위치")
    KEY_ROBOT_X:  float,
    KEY_ROBOT_Y:  float,
    KEY_ROBOT_Z:  float,
    KEY_ROBOT_W:  float,
    KEY_ROBOT_P:  float,
    KEY_ROBOT_R:  float
}

# 화면 표시용 레이블 (UI 생성 시 활용 가능)
MACRO_UI_LABELS: Dict[str, str] = {
    KEY_ROBOT_X: 'X (mm)',
    KEY_ROBOT_Y: 'Y (mm)',
    KEY_ROBOT_Z: 'Z (mm)',
    KEY_ROBOT_W: 'W (deg)',
    KEY_ROBOT_P: 'P (deg)',
    KEY_ROBOT_R: 'R (deg)'
}


# =============================================================================
# [OUTPUT] PLC 통신용
# =============================================================================
# 용도: 내부 데이터를 PLC(TwinCAT/FANUC)가 이해할 수 있는 키로 최종 변환
# 매핑: 내부 변수명(Source) -> PLC 데이터 키(Key)
# 위치: Worker의 _transform_to_fanuc_format 메서드에서 참조함
FANUC_SCHEMA: Dict[str, Dict[str, Any]] = { 
    'F': {'source': KEY_ROBOT_FEED_RATE, 'type': float},
    'X': {'source': KEY_ROBOT_X,  'type': float},
    'Y': {'source': KEY_ROBOT_Y,  'type': float},
    'Z': {'source': KEY_ROBOT_Z,  'type': float},
    'W': {'source': KEY_ROBOT_W,  'type': float},
    'P': {'source': KEY_ROBOT_P,  'type': float},
    'R': {'source': KEY_ROBOT_R,  'type': float}
}


# =============================================================================
# [OUTPUT] 서보 모터(Panasonic) 제어 설정
# =============================================================================
# 용도: 3개의 서보 모터에 대한 축 매핑, 제어 모드, 단위 변환 계수 정의
# 위치: ServoAdapter나 Executor에서 참조하여 명령 생성 시 사용
SERVO_SCHEMA: Dict[str, Dict[str, Any]] = {
    # -----------------------------------------------------------
    # Axis 1: Tool Revolution (공전)
    # -----------------------------------------------------------
    KEY_TOOL_REV_RPM: {
        'axis_index': 1,        # PLC 변수 인덱스 (vel1, pos1...)
        'control_mode': 'velocity', # 제어 방식: 속도(Velocity) vs 위치(Position)
        'scale_factor': 6.0,    # 단위 변환: RPM * 6.0 = deg/s
    },

    # -----------------------------------------------------------
    # Axis 2: Tool Rotation (자전)
    # -----------------------------------------------------------
    KEY_TOOL_ROT_RPM: {
        'axis_index': 2,
        'control_mode': 'velocity',
        'scale_factor': 6.0,    # 단위 변환: RPM * 6.0 = deg/s
    },

    # -----------------------------------------------------------
    # Axis 3: Turntable (턴테이블)
    # -----------------------------------------------------------
    KEY_TURNTABLE_DEG: {
        'axis_index': 3,
        'control_mode': 'position', # 절대 위치 이동
        'scale_factor': 1.0,    # 단위 변환: deg -> deg (변환 없음)
    }
}


# =============================================================================
# [SELECTOR] 실행기(Executor) 판별용 키 집합
# =============================================================================
# 용도: 파일 파싱 후 어떤 실행기(Executor)를 사용할지 결정할 때 사용
# 위치: twincat_commander.py 의 can_execute() 메서드들

# 1. 로봇(FANUC) 제어와 관련된 키
ROBOT_KEYS = {
    KEY_ROBOT_X, KEY_ROBOT_Y, KEY_ROBOT_Z, KEY_ROBOT_W, KEY_ROBOT_P, KEY_ROBOT_R,
    KEY_LEGACY_X, KEY_LEGACY_Y, KEY_LEGACY_Z,
    KEY_POLAR_RADIUS, KEY_PARA_HEIGHT
}

# 2. 서보(Panasonic) 제어와 관련된 키
SERVO_KEYS = {
    KEY_TURNTABLE_DEG,
    KEY_TOOL_REV_RPM,
    KEY_TOOL_ROT_RPM,
    KEY_POLAR_THETA,
    KEY_TURNTABLE_FEED_RATE
}


# =============================================================================
# [INTERNAL] 상태 관리 및 기본값
# =============================================================================
class TaskStatus:
    """작업 진행 상태"""
    UNPROCESSED = 'unprocessed' # 대기 중 (아직 시작 안 함)
    PROCESSING  = 'processing'  # 실행 중 (현재 로봇이 이동 중)
    PROCESSED   = 'processed'   # 완료됨 (이 줄은 실행 끝남)

class TaskResult:
    """작업 최종 결과"""
    PENDING   = 'pending'         # 결과 대기 (아직 모름)
    COMPLETED = 'completed'       # 성공
    FAILED    = 'failed'          # 실패 (에러 발생)


# 용도: 파일에는 없지만, 앱 구동을 위해 파서가 강제로 주입해야 하는 기본값들
# 위치: SequenceParser.parse() 메서드에서 사용됨
DEFAULT_VALUES: dict[str, str] = {
    KEY_STATUS: TaskStatus.UNPROCESSED,
    KEY_RESULT: TaskResult.PENDING
}
