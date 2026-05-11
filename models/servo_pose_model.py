# models/servo_pose_model.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any
from config.data_formats import SERVO_SCHEMA




@dataclass(frozen=True, slots=True)
class ServoPose:
    """
    서보모터 제어 데이터 모델 (앱 도메인 모델)

        목적:
            서보모터의 목표 위치와 이동 속도를 정의한다.
            
        Attributes:
            target_position (float): 목표 각도 (deg) - PLC 변수: MAIN.pos{}
            moving_velocity (float): 이동 속도 (deg/s) - PLC 변수: MAIN.vel{}
    """
    target_position: float = 0.0
    moving_velocity: float = 10.0  # 기본 이동 속도

    @property
    def angle(self) -> float:
        """Alias for target_position (UI/Logic compatibility)"""
        return self.target_position

    @property
    def velocity(self) -> float:
        """Alias for moving_velocity (UI/Logic compatibility)"""
        return self.moving_velocity

    def to_dict_preserving_key_names(self) -> Dict[str, float]:
        return asdict(self)


class ServoPoseModel:
    """
    서보모터 데이터(ServoPose) 생성을 담당하는 팩토리 클래스
    """

    @staticmethod
    def create_for_axis(data: Dict[str, Any], axis_schema_key: str) -> ServoPose:
        """
        특정 축(Axis)의 스키마 설정에 맞춰 원본 데이터로부터 ServoPose 객체를 생성한다.
        
        Args:
            data: CSV 또는 처리된 데이터 딕셔너리
            axis_schema_key: SERVO_SCHEMA에 정의된 키 (예: 'spindle_revolution_velocity', 'turntable_target_position')
        """
        
        # 1. 축 스키마 정보 확인
        if axis_schema_key not in SERVO_SCHEMA:
            # 정의되지 않은 축이면 안전하게 기본값 반환
            return ServoPose()
            
        axis_config = SERVO_SCHEMA[axis_schema_key]
        
        # 2. 데이터 추출
        # data에는 이미 CSV 파서가 내부 이름으로 변환한 값이 들어있음
        raw_value = data.get(axis_schema_key, 0.0)
        
        # 3. 물리 단위 변환 (Scale Factor 적용)
        # 예: RPM -> deg/s (1 RPM = 6 deg/s)
        scale_factor = axis_config.get('scale_factor', 1.0)
        calculated_value = float(raw_value) * scale_factor
        
        # 4. 제어 모드(위치/속도)에 따른 객체 생성
        control_mode = axis_config.get('control_mode', 'velocity')
        
        if control_mode == 'position':
            # [위치 제어 모드] - 전형적으로 턴테이블
            # 데이터 값은 '목표 회전 위치'로 간주함
            # 속도는 별도의 'turntable_velocity' 키에서 가져오거나 기본값 사용 (config mapping 기반)
            
            target_velocity = data.get('turntable_velocity', 10.0)
            
            return ServoPose(
                target_position=calculated_value,
                moving_velocity=float(target_velocity)
            )
            
        else: # 'velocity'
            # [속도 제어 모드] - 전형적으로 공전/자전 spindle
            # 데이터 값은 '회전 속도'로 간주함
            # 목표 위치(target_position)는 의미 없으므로 0.0으로 고정
            
            return ServoPose(
                target_position=0.0,
                moving_velocity=calculated_value
            )
