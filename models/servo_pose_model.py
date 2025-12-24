# models/servo_pose_model.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any
from config.data_formats import SERVO_SCHEMA




@dataclass(frozen=True, slots=True)
class ServoPose:
    """
    서보모터 제어 데이터 모델

        목적:
            서보모터의 목표 각도와 회전 속도를 정의
            
        Attributes:
            angle (float): 목표 각도 (deg) - PLC 변수: MAIN.position
            velocity (float): 회전 속도 (deg/s) - PLC 변수: MAIN.velocity
    """
    angle: float = 0.0
    velocity: float = 10.0  # 기본 속도

    def to_dict_preserving_key_names(self) -> Dict[str, float]:
        return asdict(self)


class ServoPoseModel:
    """
    서보모터 데이터 생성 팩토리
    """

    @staticmethod
    def create_for_axis(data: Dict[str, Any], axis_key: str) -> ServoPose:
        """
        특정 축(Axis)의 설정(Schema)에 맞춰 데이터를 추출하고 ServoPose 객체 생성
        
        Args:
            data: CSV/TXT 파일에서 파싱된 데이터 행 (Dict)
            axis_key: SERVO_SCHEMA에 정의된 키 (예: 'tool_revolution_rpm', 'turntable_deg')
        """
        
        # 1. 해당 축의 스키마 정보 가져오기 (없으면 에러 또는 기본값)
        if axis_key not in SERVO_SCHEMA:
            # 정의되지 않은 축이면 기본값 반환 (안전장치)
            return ServoPose()
            
        schema = SERVO_SCHEMA[axis_key]
        
        # 2. 메인 값 추출 (예: RPM 또는 각도)
        # data 딕셔너리에는 이미 CSV/TXT 파서가 'internal name'으로 변환해둔 값이 들어있음
        raw_val = data.get(axis_key, 0.0)
        
        # 3. 스케일링 적용 (config에 정의된 scale_factor 사용)
        # 예: RPM(100) * 6.0 = 600 deg/s
        scale = schema.get('scale_factor', 1.0)
        scaled_val = float(raw_val) * scale
        
        # 4. 제어 모드에 따라 Angle/Velocity 구분
        mode = schema.get('control_mode', 'velocity')
        
        if mode == 'position':
            # [위치 제어 모드] - 예: 턴테이블
            # 메인 값 = 각도 (Angle)
            # 속도 값 = 별도 키('turntable_feed_rate')에서 찾거나 기본값
            
            # TODO: 나중에 'turntable_feed_rate' 키 이름도 스키마에서 관리하면 더 좋음
            feed_val = data.get('turntable_feed_rate', 10.0)
            
            return ServoPose(
                angle=scaled_val,
                velocity=float(feed_val)
            )
            
        else: # 'velocity'
            # [속도 제어 모드] - 예: 툴 공전/자전
            # 메인 값 = 속도 (Velocity)
            # 각도 = 0.0 (의미 없음)
            
            return ServoPose(
                angle=0.0,
                velocity=scaled_val
            )
