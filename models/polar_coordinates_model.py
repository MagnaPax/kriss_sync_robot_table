from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass(frozen=True, slots=True)
class PolarCoordinates:
    """
    턴테이블 극좌표계 표현
        내부 로직용: ViewModel, Service, Worker 사이에서 데이터를 주고받을 때 사용
        
    Attributes:
        r : 반지름 (distance)
        theta : 회전각 (degree 또는 rad)
        feed : 속도 정보(optional)
    """
    r: float = 0.0
    theta: float = 0.0
    feed: float = 0.0   # FANUCPose와 동일한 인터페이스 유지

    def to_dict(self) -> Dict[str, float]:
        return {"f": self.feed, "r": self.r, "theta": self.theta}


class PolarCoordinatesModel:
    """
    순수 비즈니스 로직
    FANUCPoseModel 과 동일한 구조의 파서(parser) 제공
    """

    @staticmethod
    def parse_from_data(data: Dict[str, Any]) -> Dict[str, PolarCoordinates]:
        """
        매크로 딕셔너리 데이터를 PolarCoordinates 객체로 변환
        """
        if not isinstance(data, dict):
            raise TypeError("극좌표 매크로 데이터는 dict 형식이어야 합니다.")

        result: Dict[str, PolarCoordinates] = {}

        for macro_id, macro_data in data.items():
            if not isinstance(macro_data, dict):
                raise ValueError(f"매크로 '{macro_id}'의 데이터가 dict가 아닙니다.")

            pose = PolarCoordinatesModel._create(data=macro_data, macro_id=macro_id)
            result[macro_id] = pose

        if not result:
            raise ValueError("로드된 턴테이블 매크로가 하나도 없습니다.")

        return result

    @staticmethod
    def _create(data: Dict[str, Any], macro_id: str) -> PolarCoordinates:

        def get_float(key: str) -> float:
            value = data.get(key)
            if value is None:
                raise KeyError(f"매크로 '{macro_id}'에 필수 키 '{key}'가 없습니다.")
            try:
                return float(value)
            except (TypeError, ValueError):
                raise ValueError(f"매크로 '{macro_id}'의 '{key}' 값이 숫자가 아닙니다: {value}")

        return PolarCoordinates(
            r=get_float("r"),
            theta=get_float("theta"),
            feed=float(data.get("f", 0.0))  # FANUC 형식과 동일하게 'f' 사용
        )

    @staticmethod
    def get_coordinate(macros: Dict[str, PolarCoordinates], macro_id: str) -> PolarCoordinates:
        try:
            return macros[macro_id]
        except KeyError:
            raise KeyError(f"매크로 '{macro_id}'를 찾을 수 없습니다.")
