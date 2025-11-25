# utils/coordinate_utils.py
"""
dict → list 변환 유틸리티 모듈
"""
from typing import Dict, List, Any

AXIS_ORDER = ["x", "y", "z", "w", "p", "r"]




def dict_to_axis_list(coords: Dict[str, Any]) -> List[float]:
    """
    dict {"x":1, "y":2 ...} → [1,2, ...] 로 변환
    """
    return [float(coords[axis]) for axis in AXIS_ORDER]
