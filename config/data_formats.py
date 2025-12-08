# config/data_formats.py
"""
데이터 파일 형식 명세 (Schema Definitions)
---------------------------------------
TXT, CSV 파서 및 매크로 저장 시 사용되는 컬럼 순서와 키 매핑을 정의

사용법:
    from config.data_formats import TXT_SCHEMA, CSV_SCHEMA, MACRO_SCHEMA

    field_keys = list(TXT_SCHEMA.keys())
    print(field_keys)
"""

from typing import List, Dict



# =============================================================================
# CSV 파일 형식
# =============================================================================
CSV_SCHEMA: dict[str, dict] = {
    'PRLINE': {'name': 'id','type': int},                   # 시퀀스 번호
    'F': {'name': 'turntable_feed_rate','type': float},     # 초당 회전속도 (feed rate)
    'U': {'name': 'polar_coord_theta',  'type': float},     # 각도 (극좌표계의 θ)
    'X': {'name': 'polar_coord_radius', 'type': float},     # 반지름 (극좌표계의 r)
    'Z': {'name': 'paraboloid_height',  'type': float},     # 파라볼로이드 높이 (쌍곡포물면)
    'A': {'name': 'untitle',            'type': float},     # 의미 없음. 그냥 0
    'B': {'name': 'tool_stroke_rpm',    'type': float},     # 툴 스트로크 속도 (rpm)
}


# =============================================================================
# TXT 파일 형식 (순서가 중요함)
# =============================================================================
TXT_SCHEMA: dict[str, dict] = {
    'F': {'name': 'robot_feed_rate',     'type': float},     # 로봇 이동 속도 (mm/sec)
    'T': {'name': 'turntable_deg',       'type': float},     # 턴테이블 각도 (deg)
    'X': {'name': 'x_coord',             'type': float},     # X 좌표 (mm)
    'Y': {'name': 'y_coord',             'type': float},     # Y 좌표 (mm)
    'Z': {'name': 'z_coord',             'type': float},     # Z 좌표 (mm)
    'W': {'name': 'w_angle',             'type': float},     # W 각도 (deg)
    'P': {'name': 'p_angle',             'type': float},     # P 각도 (deg)
    'R': {'name': 'r_angle',             'type': float},     # R 각도 (deg)
    'M': {'name': 'tool_rotation_rpm',   'type': float},     # 툴 자전 속도 (rpm)
    'N': {'name': 'tool_revolution_rpm', 'type': float}      # 툴 공전 속도 (rpm)
}


# =============================================================================
# 매크로 데이터 형식
# =============================================================================
# 매크로 저장 시 사용되는 키 목록 (검증용)
MACRO_SCHEMA: dict[str, type] = {
    'macro_id': str,
    'name': str,
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
# FANUC 실행용
# =============================================================================
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
# DEFAULT_VALUES 관리 상수 (오타 방지용)
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


# =============================================================================
# 시퀀스 처리 상태 (원본 CSV 파일에는 없지만 내부적으로 필요한 필드들)
# =============================================================================
DEFAULT_VALUES: dict[str, str] = {
    'status': TaskStatus.UNPROCESSED,
    'result': TaskResult.PENDING
}












# =============================================================================
# 통합 데이터 스키마
# =============================================================================

# 통합 데이터 스키마
UNIFIED_DATA: dict[str, type] = {

    # 1. 메타 데이터 (추적용)
    'source':   str,    # 데이터 출처 (예: "UI", "TXT", "CSV")
    'name':     str,    # 명령 이름 (예: "GoTo", "Macro_1")
    'seq_id':   int,    # [CSV] PRLINE (시퀀스 번호)

    # 로봇 제어
    'feed':     float,  # robot_feed_rate
    'x':        float,  # x_coord
    'y':        float,  # y_coord
    'z':        float,  # z_coord
    'w':        float,  # w_angle
    'p':        float,  # p_angle
    'r':        float,  # r_angle
    'rpm_rot':  float,  # tool_rotation_rpm (M)
    'rpm_rev':  float,  # tool_revolution_rpm (N)
    
    # 턴테이블
    'tt_feed':  float,  # turntable_feed_rate
    'radius':   float,  # polar_coord_radius
    'theta':    float,  # polar_coord_theta
    'para_z':   float,  # paraboloid_height
    'stroke':   float,  # tool_stroke_rpm

    # 기타
    'dummy':    float   # [CSV] A (의미 없는 더미 값)
}
