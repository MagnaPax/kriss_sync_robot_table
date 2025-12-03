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
# TXT 파일 형식 (순서가 중요함)
# =============================================================================
TXT_SCHEMA: dict[str, type] = {
    'feed':                float,  # 1번째: F
    'turntable_deg':       float,  # 2번째: T
    'x_coord':             float,  # 3번째: X
    'y_coord':             float,  # 4번째: Y
    'z_coord':             float,  # 5번째: Z
    'w_angle':             float,  # 6번째: W
    'p_angle':             float,  # 7번째: P
    'r_angle':             float,  # 8번째: R
    'tool_rpm_rotation':   float,  # 9번째: M (혹시 정수라면 int로 변경 가능)
    'tool_rpm_revolution': float   # 10번째: N
}


# =============================================================================
# CSV 파일 형식
# =============================================================================
CSV_SCHEMA: dict[str, dict] = {
    'F': {'name': 'feed_rate',          'type': float},     # 초당 회전속도 (feed rate)
    'U': {'name': 'polar_coord_theta',  'type': float},     # 각도 (극좌표계의 θ)
    'X': {'name': 'polar_coord_radius', 'type': float},     # 반지름 (극좌표계의 r)
    'Z': {'name': 'paraboloid_height',  'type': float},     # 파라볼로이드 높이
    'B': {'name': 'tool_stroke_rpm',    'type': float},     # 툴 스트로크 속도 (rpm)
    # 'PRLINE': 시퀀스 번호는 별도 로직으로 처리
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
