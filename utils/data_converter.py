# utils/data_converter.py

from typing import Any, Dict
from config.data_formats import UNIFIED_DATA



def to_unified_format(source_data: Dict[str, Any], source_type: str = "UNKNOWN") -> Dict[str, Any]:
    """
    다양한 형태의 입력 데이터를 '통합 스키마(UNIFIED_DATA)' 형태로 정규화
    """
    unified_data = {}

    # 키 매핑 : 입력 데이터의 'name'들 -> 통합 스키마 키
    #    서로 다른 이름을 가진 키들을 '통합 키'로 연결
    key_map = {
        # --- 공통/메타 ---
        'seq_id':   ['id', 'PRLINE'],  # CSV의 id

        # --- 로봇 (TXT) ---
        'feed':     ['robot_feed_rate', 'F'],
        'x':        ['x_coord', 'x', 'X'],
        'y':        ['y_coord', 'y', 'Y'],
        'z':        ['z_coord', 'z', 'Z'], # 직교 Z
        'w':        ['w_angle', 'w', 'W'],
        'p':        ['p_angle', 'p', 'P'],
        'r':        ['r_angle', 'r', 'R'],
        'rpm_rot':  ['tool_rotation_rpm', 'M'],
        'rpm_rev':  ['tool_revolution_rpm', 'N'],

        # --- 턴테이블 (CSV) ---
        'tt_feed':  ['turntable_feed_rate'], # CSV의 F
        'radius':   ['polar_coord_radius'],  # CSV의 X
        'theta':    ['polar_coord_theta'],   # CSV의 U
        'para_z':   ['paraboloid_height'],   # CSV의 Z (파라볼로이드 높이)
        'stroke':   ['tool_stroke_rpm'],     # CSV의 B
        'dummy':    ['untitle']              # CSV의 A
    }

    # 데이터 추출 및 변환
    for unified_key, default_type in UNIFIED_DATA.items():
        found_value = None

        # 1. 메타 데이터 처리
        if unified_key == 'source':
            unified_data['source'] = source_type
            continue

        # 2. 후보 키들을 뒤져서 값이 있는지 확인
        candidates = key_map.get(unified_key, [unified_key])
        for cand in candidates:
            if cand in source_data:
                found_value = source_data[cand]
                break

        # 3. 값이 없으면 기본값(0.0 or 빈문자열), 있으면 타입 변환
        if found_value is None:
            unified_data[unified_key] = default_type() # 0.0 or ""
        else:
            try:
                unified_data[unified_key] = default_type(found_value)
            except ValueError:
                unified_data[unified_key] = default_type()

    return unified_data