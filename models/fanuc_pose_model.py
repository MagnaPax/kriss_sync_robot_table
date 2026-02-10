# models/fanuc_pose_model.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any
import ctypes
import math
from config.data_formats import (
    KEY_ROBOT_X, KEY_ROBOT_Y, KEY_ROBOT_Z, KEY_ROBOT_W, KEY_ROBOT_P, KEY_ROBOT_R, 
    KEY_ROBOT_FEED_RATE, KEY_TURNTABLE_FEED_RATE, KEY_TURNTABLE_DEG
)


@dataclass(frozen=True, slots=True)
class FANUCPose:
    """
    FANUC 로봇 좌표 데이터 모델 (앱 도메인 모델)

        목적:
            로봇 포즈를 사람이 이해하기 좋은 형태로 표현한 값
            실제 로봇 포즈 저장
            
        용도:
            내부 로직용: ViewModel, Service, Worker 사이에서 데이터를 주고받을 때 사용

        역할:
            데이터 모델

        동작:
            좌표 데이터가 상태(state)
        
        Attributes:
            x (float): X축 좌표 (mm) - 로봇 베이스 기준 전후
            y (float): Y축 좌표 (mm) - 로봇 베이스 기준 좌우
            z (float): Z축 좌표 (mm) - 로봇 베이스 기준 상하
            w (float): W (Yaw) - X축 기준 회전 각도 (deg)
            p (float): P (Pitch) - Y축 기준 회전 각도 (deg)
            r (float): R (Roll) - Z축 기준 회전 각도 (deg)
            f (float): Feed Rate - 이동 속도 (mm/sec)
    """
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 0.0
    p: float = 0.0
    r: float = 0.0
    f: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FANUCPose':
        """
        딕셔너리(CSV Row 등)에서 FANUCPose 객체 생성
        """
        return cls(
            x=float(data.get(KEY_ROBOT_X, 0.0)),
            y=float(data.get(KEY_ROBOT_Y, 0.0)),
            z=float(data.get(KEY_ROBOT_Z, 0.0)),
            w=float(data.get(KEY_ROBOT_W, 0.0)),
            p=float(data.get(KEY_ROBOT_P, 0.0)),
            r=float(data.get(KEY_ROBOT_R, 0.0)),
            f=float(data.get(KEY_ROBOT_FEED_RATE, 0.0))
        )

    def to_dict_with_meaningful_names(self) -> Dict[str, float]:
        return {"robot_feed_rate":self.f, "axis_x": self.x, "axis_y": self.y, "axis_z": self.z, "yaw_w": self.w, "pitch_p": self.p, "roll_r": self.r}
    
    def to_dict_preserving_key_names(self) -> Dict[str, Any]:
        # dataclasses.asdict를 쓰면 자동으로 딕셔너리가 된다(키값은 똑같음)
        return asdict(self)


class FANUCPoseModel:
    """
    FANUCPose 객체 생성을 담당하는 팩토리(Factory) 및 검증 클래스
    
    역할:
        1. 외부 데이터(JSON, Dict)의 유효성 검사 (Validation)
        2. 안전한 타입 변환 (str -> float)
        3. 도메인 객체(FANUCPose) 생성 및 반환
        
    이 클래스는 상태를 가지지 않으므로(Stateless), 모든 메서드는 정적(@staticmethod)이다
    """

    @staticmethod
    def pre_calculate_all(data: list[Any]) -> list[dict[str, float]]:
        """
        데이터 가공(Delta 구하기)
            
        Returns:
            list[dict]: [{'dx': float, 'dz': float, 'fd': float}, ...] 형태의 리스트
        """
        all_data = [] 
        prev_u = None; prev_x = None; prev_z = None

        for item in data:

            try:
                f_val   = float(item.get(KEY_TURNTABLE_FEED_RATE, 0.0))
                curr_u  = float(item.get(KEY_TURNTABLE_DEG, 0.0))
                curr_x  = float(item.get(KEY_ROBOT_X, 0.0))
                curr_z  = float(item.get(KEY_ROBOT_Z, 0.0))
            except (ValueError, TypeError):
                continue

            if prev_u is not None:
                delta_u = curr_u - prev_u
                if delta_u < 0: delta_u += 360
                delta_x = curr_x - prev_x
                delta_z = curr_z - prev_z
            else:
                delta_u = curr_u
                delta_x = curr_x
                delta_z = curr_z

            if delta_u != 0:
                moving_time = delta_u / f_val
                distance = math.sqrt(delta_x ** 2 + delta_z ** 2)
                robot_feed = round(distance / moving_time, 3)
                all_data.append({
                    'dx': delta_x, 
                    'dz': delta_z, 
                    'fd': robot_feed
                })
            elif delta_u == 0:
                robot_feed = 10.0
                all_data.append({
                    'dx': round(delta_x, 3),
                    'dz': round(delta_z, 3),
                    'fd': robot_feed
                })    

            prev_u = curr_u
            prev_x = curr_x
            prev_z = curr_z
            
        return all_data
