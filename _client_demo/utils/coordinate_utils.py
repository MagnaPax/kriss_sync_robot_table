# utils/coordinate_utils.py
from typing import Dict, List, Any

# 가능한 모든 키 매핑 (대문자, 소문자, _coord 형태, feed 등)
KEY_MAPPING = {
    'x': ['x', 'X', 'x_coord'],
    'y': ['y', 'Y', 'y_coord'],
    'z': ['z', 'Z', 'z_coord'],
    'w': ['w', 'W', 'w_angle'],
    'p': ['p', 'P', 'p_angle'],
    'r': ['r', 'R', 'r_angle'],
    'f': ['f', 'F', 'feed']  # F는 feed
}

def dict_to_axis_list(coords: Dict[str, Any]) -> List[float]:
    """
    어떤 형태의 키든 상관없이 좌표 리스트로 변환
    - UI 입력: {'X': '15.84', 'Y': '11.87', ...}
    - 파일 파싱 후: {'x_coord': 95.8, 'feed': 10, ...}
    - 모두 안전하게 처리 + 공백 제거
    """
    result = []
    for axis in ['x', 'y', 'z', 'w', 'p', 'r', 'f']:
        value = None
        for possible_key in KEY_MAPPING[axis]:
            if possible_key in coords:
                value = coords[possible_key]
                break
        if value is None:
            raise KeyError(f"좌표 키를 찾을 수 없습니다: {axis} (가능한 키: {KEY_MAPPING[axis]})")
        
        # 문자열이면 strip 후 변환
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                raise ValueError(f"{axis} 값이 비어있습니다.")
            value = float(cleaned)
        else:
            value = float(value)
        
        result.append(value)
    
    return result
