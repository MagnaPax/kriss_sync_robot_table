# models/servo_pose_model.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any



@dataclass(frozen=True, slots=True)
class ServoPose:
    """
    턴테이블 제어 데이터 모델

        목적:
            턴테이블의 목표 각도와 회전 속도를 정의
            
        Attributes:
            angle (float): 목표 각도 (deg) - PLC 변수: MAIN.position
            velocity (float): 회전 속도 (deg/s) - PLC 변수: MAIN.velocity
    """
    angle: float = 0.0
    velocity: float = 10.0  # 기본 속도 (안전값)

    def to_dict_preserving_key_names(self) -> Dict[str, float]:
        return asdict(self)


class ServoPoseModel:
    """
    턴테이블 관련 비즈니스 로직 (파싱, 생성 등)
    """

    @staticmethod
    def create_from_data(data: Dict[str, Any]) -> ServoPose:
        """
        데이터 딕셔너리에서 ServoPose 객체 생성
        
        Args:
            data: {'turntable_deg': 90.0, 'turntable_feed_rate': 20.0, ...}
                또는 {'angle': 90.0, 'velocity': 20.0}
        """

        # 1. 각도(Angle) 찾기 
        # (CSV_SCHEMA의 'turntable_deg' 또는 TXT_SCHEMA의 'T' 대응)
        angle = data.get('angle') or data.get('turntable_deg') or data.get('T', 0.0)

        # 2. 속도(Velocity) 찾기
        # (CSV_SCHEMA의 'turntable_feed_rate' 대응)
        velocity = data.get('velocity') or data.get('turntable_feed_rate', 10.0)

        return ServoPose(
            angle=float(angle),
            velocity=float(velocity)
        )
