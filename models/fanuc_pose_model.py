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

    def distance_to(self, target: 'FANUCPose') -> tuple[float, float]:
        """
        현재 위치(self)와 목표 위치(target) 간의 거리 계산
        
        [Reference]
        원본 파일: 260102.FANUC_FULL_THREADING.py
        원본 함수: calculate_distance(current_pos, target_pos)
        
        Returns:
            (linear_dist, angular_dist): (직선 거리 mm, 최대 회전 각도 deg)
        """
        dx = target.x - self.x
        dy = target.y - self.y
        dz = target.z - self.z
        linear_dist = math.sqrt(dx**2 + dy**2 + dz**2)

        dw = abs(target.w - self.w)
        dp = abs(target.p - self.p)
        dr = abs(target.r - self.r)
        angular_dist = max(dw, dp, dr)
        
        return linear_dist, angular_dist

    def to_struct(self, prev_pose: 'FANUCPose', signals: Dict[Any, bool]) -> FanucCommandPacket:
        """
        [핵심] 도메인 포즈 객체 -> PLC 전송용 구조체(24byte) 변환

        [Reference]
        원본 파일: 260102.FANUC_FULL_THREADING.py
        원본 함수: pack_fanuc_payload(coords, deltas, signals)

        Args:
            prev_pose (FANUCPose): 이전 위치 (Delta 계산용)
            signals (Dict[Any, bool]): 제어 신호 ('IMSP', 'Hold', 'Start' 등)

        Returns:
            FanucCommandPacket: PLC에 곧바로 쓸 수 있는 ctypes 구조체
        """
        payload = FanucCommandPacket()

        # 1. 신호 패킹 (UI_Byte1, UI_Byte2, UI_Byte3 일부)
        # ---------------------------------------------------------------------
        # UI_Byte1
        b1 = 0
        if signals.get('IMSP', True):      b1 |= (1 << 0)
        if signals.get('Hold', True):      b1 |= (1 << 1)
        if signals.get('SFSP', True):      b1 |= (1 << 2)
        if signals.get('CycleStop', False): b1 |= (1 << 3)
        if signals.get('FaultReset', False):b1 |= (1 << 4)
        if signals.get('Start', False):     b1 |= (1 << 5)
        if signals.get('Home', False):      b1 |= (1 << 6)
        if signals.get('Enable', True):     b1 |= (1 << 7)
        payload.UI_Byte1 = b1

        # UI_Byte2
        b2 = 0
        if signals.get('RSR1', False): b2 |= (1 << 0)
        if signals.get('RSR2', False): b2 |= (1 << 1)
        if signals.get('RSR3', False): b2 |= (1 << 2)
        if signals.get('RSR4', False): b2 |= (1 << 3)
        if signals.get('RSR5', False): b2 |= (1 << 4)
        if signals.get('RSR6', False): b2 |= (1 << 5)
        if signals.get('RSR7', False): b2 |= (1 << 6)
        if signals.get('RSR8', False): b2 |= (1 << 7)
        payload.UI_Byte2 = b2

        # UI_Byte3 (하위 4비트: 신호 / 상위 4비트: Feed High)
        b3 = 0
        if signals.get('PNSStrobe', False): b3 |= (1 << 0)
        if signals.get('ProdStart', False): b3 |= (1 << 1)
        if signals.get('DI43', False):      b3 |= (1 << 2)
        if signals.get('DI44', False):      b3 |= (1 << 3)
        
        # 2. Feed Rate 패킹 (자신의 속도 f 사용)
        # ---------------------------------------------------------------------
        # 공식: int(abs(round(val, 3) * 1000))
        raw_feed_rate = int(abs(round(self.f, 3) * 1000))
        
        # 상위 4비트 -> UI_Byte3 상위
        feed_high = (raw_feed_rate >> 16) & 0x0F
        b3 |= (feed_high << 4)
        payload.UI_Byte3 = b3
        
        # 하위 16비트 -> Feed_Low
        payload.Feed_Low = raw_feed_rate & 0xFFFF

        # 3. 좌표 Delta 패킹 (X, Y, Z, W, P, R)
        # ---------------------------------------------------------------------
        deltas = {
            'X': self.x - prev_pose.x,
            'Y': self.y - prev_pose.y,
            'Z': self.z - prev_pose.z,
            'W': self.w - prev_pose.w,
            'P': self.p - prev_pose.p,
            'R': self.r - prev_pose.r
        }

        # 축 순서 중요 (구조체 필드 순서와 비트 순서 일치)
        axes = ['X', 'Y', 'Z', 'W', 'P', 'R']
        check_byte = 0

        for i, axis in enumerate(axes):
            val = deltas[axis]
            
            # 정수 변환 (절댓값)
            int_val = int(abs(round(val, 3) * 1000))
            
            # 구조체 필드에 할당 (동적 속성 할당)
            # 예: payload.X_High = ...
            setattr(payload, f"{axis}_High", (int_val >> 16) & 0xFF)
            setattr(payload, f"{axis}_Low", int_val & 0xFFFF)
            
            # 음수 체크 비트 설정
            if val < 0:
                check_byte |= (1 << i)

        payload.Check_Bits = check_byte

        return payload

    @classmethod
    def create_signal_only_packet(cls, signals: Dict[Any, bool]) -> FanucCommandPacket:
        """
        좌표 이동 없이 '신호(Signal)'만 전송하기 위한 패킷 생성
        
        설명:
            로봇의 이동이 목적이 아니라 Start/Stop/Reset 등의 제어 신호만 전송하고 싶을 때.
            내부적으로 0.0 좌표를 가진 객체를 생성하여 to_struct를 호출한다.

        Args:
            signals (Dict[Any, bool]): 전송할 제어 신호들

        Returns:
            FanucCommandPacket: 신호가 담긴 전송용 구조체
        """
        empty_pose = cls() # (0,0,0,0,0,0)
        return empty_pose.to_struct(empty_pose, signals)


# [변경] FanucUI1Struct -> FanucCommandPacket (더 직관적인 이름)
class FanucCommandPacket(ctypes.Structure):
    """
    FANUC 로봇 제어 명령 패킷 (24 Byte)
    
    [구조 설명]
    이 구조체는 Beckhoff PLC의 'MAIN.Robot1._UI1' 주소와 정확히 1:1 매핑됩니다.
    
    - UI_Byte1, 2, 3: 로봇 제어 신호(Start, Hold 등)와 Feed Rate의 상위 비트가 포함됨.
    - Feed_Low: Feed Rate의 하위 16비트.
    - X/Y/Z/W/P/R High/Low: 
      각 축의 이동량(Delta)을 1000배 하여 정수화한 값. 
      High(8bit) + Low(16bit) = 24bit Integer 표현.
    - Check_Bits: 각 축의 이동량이 음수(-)인지 표시하는 부호 비트들의 모음.

    Reference:
        - FanucUI1Struct in 260102.FANUC_FULL_THREADING.py
        - PLC Definition: docs/plc/DUT_FANUC_UI1.st
    """
    _pack_ = 1
    _fields_ = [
        ("UI_Byte1", ctypes.c_uint8),   # CycleStop, FaultReset, Start, Home, Enable
        ("UI_Byte2", ctypes.c_uint8),   # RSR1, RSR2, RSR3
        ("UI_Byte3", ctypes.c_uint8),   # PNSStrobe, ProdStart, DI43, DI44
        ("Feed_Low", ctypes.c_uint16),
        ("X_High", ctypes.c_uint8), ("X_Low",  ctypes.c_uint16),
        ("Y_High", ctypes.c_uint8), ("Y_Low",  ctypes.c_uint16),
        ("Z_High", ctypes.c_uint8), ("Z_Low",  ctypes.c_uint16),
        ("W_High", ctypes.c_uint8), ("W_Low",  ctypes.c_uint16),
        ("P_High", ctypes.c_uint8), ("P_Low",  ctypes.c_uint16),
        ("R_High", ctypes.c_uint8), ("R_Low",  ctypes.c_uint16),
        ("Check_Bits", ctypes.c_uint8)
    ]


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

    def do_task(self) -> str:
        msg: str = "Hello, MVVM"
        return msg
    

    @staticmethod
    def parse_poses_from_data(data: Dict[str, Any]) -> Dict[str, FANUCPose]:
        """
        매크로 파일 내용(Dict)을 파싱하여 FANUCPose 객체들의 딕셔너리로 변환

        설명:
            파일에서 읽어온 Raw Data를 
            앱에서 안전하게 쓸 수 있는 객체(Object)로 대량 변환
            그 과정에서 데이터 구조가 올바른지 검사

        Args:
            data (Dict[str, Any]): JSON 파일에서 로드한 원본 데이터
                                예: {'Macro_1': {'x': 100, ...}, ...}

        Returns:
            Dict[str, FANUCPose]: 변환된 매크로 ID와 포즈 객체의 맵
                                예: {'Macro_1': FANUCPose(...), ...}

        Raises:
            TypeError: 입력받은 데이터가 딕셔너리가 아닐 때
            ValueError: 내부 데이터 구조가 잘못되었거나, 데이터가 비어있을 때
        """

        result: Dict[str, FANUCPose] = {}

        for macro_id, macro_data in data.items():
            if not isinstance(macro_data, dict):
                raise ValueError(f"매크로 '{macro_id}'의 데이터 형식이 올바르지 않습니다 (dict여야 함).")

            # 개별 포즈 생성 위임
            pose = FANUCPoseModel._create_pose(macro_data, macro_id)
            result[macro_id] = pose

        if not result:
            raise ValueError("로드된 매크로 데이터가 없습니다 (빈 파일).")

        return result

    @staticmethod
    def _create_pose(macro_data: Dict[str, Any], macro_id: str) -> FANUCPose:
        """
        (내부 헬퍼) 단일 딕셔너리 데이터를 FANUCPose 객체로 변환한다

        설명:
            - 필수 키(x, y, z, w, p, r)가 모두 있는지 검사
            - 값이 숫자로 변환 가능한지 확인 (문자열 "10.5" -> 실수 10.5)
            - 하나라도 문제가 있으면 즉시 에러를 발생시켜 잘못된 데이터가 흐르는 것을 방지

        Args:
            macro_data (Dict): 매크로 하나의 데이터 (예: {'x': 10, 'y': 20 ...})
            macro_id (str): 에러 메시지에 표시할 매크로 ID

        Returns:
            FANUCPose: 생성된 불변(Frozen) 데이터 객체
        """
        def get_float(key: str) -> float:
            value = macro_data.get(key)
            if value is None:
                raise KeyError(f"매크로 '{macro_id}' 데이터에 필수 키 '{key}'가 누락되었습니다.")
            try:
                return float(value)
            except (TypeError, ValueError):
                raise ValueError(f"매크로 '{macro_id}'의 '{key}' 값이 숫자가 아닙니다: {value}")

        # feed rate는 필수가 아니므로 get을 사용 (기본값 0.0)
        feed_rate_val = macro_data.get('feed_rate', macro_data.get('f', 0.0))
        try:
            feed_rate_val = float(feed_rate_val)
        except:
            feed_rate_val = 0.0

        return FANUCPose(
            x=get_float("x"),
            y=get_float("y"),
            z=get_float("z"),
            w=get_float("w"),
            p=get_float("p"),
            r=get_float("r"),
            f=feed_rate_val
        )

    @staticmethod
    def get_pose(macros: Dict[str, FANUCPose], macro_id: str) -> FANUCPose:
        """
        변환된 매크로 목록에서 특정 ID의 포즈를 안전하게 가져온다

        설명:
            단순히 macros[id]를 하는 것보다, 
            찾는 키가 없을 때 더 명확한 에러 메시지를 제공하기 위해 사용

        Args:
            macros (Dict): 파싱이 완료된 FANUCPose 딕셔너리
            macro_id (str): 찾고 싶은 매크로 ID

        Returns:
            FANUCPose: 해당 ID의 포즈 객체

        Raises:
            KeyError: 해당 ID가 존재하지 않을 때
        """
        try:
            return macros[macro_id]
        except KeyError:
            raise KeyError(f"요청한 매크로 ID '{macro_id}'를 찾을 수 없습니다.")





# ==========================================================
# Smoke Test
"""
실행 명령어
python -m models.pose_model
"""
# ==========================================================
if __name__ == '__main__':
    
    print("=" * 70)
    print("FANUCPoseModel 단독 실행 테스트")
    print("=" * 70)

    # --- 테스트용 샘플 데이터 ---
    # (MacroSettingsDialog가 생성하는 JSON 파일의 내용과 유사)
    sample_json_data = {
        "Macro_1": {
            "macro_id": "Macro_1", 
            "name": "매크로 1 이름", 
            "x": 100.1, 
            "y": 200.2, 
            "z": 0.0, 
            "w": 0.0, 
            "p": 0.0, 
            "r": 10.0
        },
        "Macro_2": {
            "macro_id": "Macro_2", 
            "name": "매크로 2 이름", 
            "x": 111.0, 
            "y": 222.0, 
            "z": 333.0, 
            "w": 44.0, 
            "p": 55.0, 
            "r": 66.0
        }
    }

    # 파싱 결과를 담을 변수를 미리 초기화한다
    poses: Dict[str, FANUCPose] = {}

    # 1. 파싱 성공 테스트
    print("\n1️⃣  파싱 성공 테스트:")
    try:
        poses = FANUCPoseModel.parse_poses_from_data(sample_json_data)
        print(f"   ✅ 파싱 성공. {len(poses)}개 매크로 로드됨.")
        print(f"   Macro_1 FANUCPose: {poses['Macro_1']}")
        print(f"   Macro_2 FANUCPose: {poses['Macro_2']}")
        
        # 2. 특정 FANUCPose 가져오기 테스트
        print("\n2️⃣  get_pose() 성공 테스트:")
        pos1 = FANUCPoseModel.get_pose(poses, "Macro_1")
        print(f"   ✅ 'Macro_1' 가져오기 성공: {pos1}")
        assert pos1.x == 100.1
        
    except (TypeError, ValueError, KeyError) as e:
        print(f"   ❌ 테스트 실패: {e}")

    # 3. 파싱 실패 테스트 (필수 키 누락)
    print("\n3️⃣  파싱 실패 테스트 (필수 키 'x' 누락):")
    invalid_data_missing_key = {
        "Macro_Bad": { "y": 1.0, "z": 1.0, "w": 0, "p": 0, "r": 0 }
    }
    try:
        FANUCPoseModel.parse_poses_from_data(invalid_data_missing_key)
    except KeyError as e:
        print(f"   ✅ 의도된 예외 발생(KeyError): {e}") #
    except Exception as e:
        print(f"   ❌ 잘못된 예외 발생: {type(e).__name__}: {e}")

    # 4. 파싱 실패 테스트 (잘못된 값 타입)
    print("\n4️⃣  파싱 실패 테스트 (잘못된 값 타입):")
    invalid_data_bad_type = {
        "Macro_Bad2": { "x": "NotANumber", "y": 1, "z": 1, "w": 0, "p": 0, "r": 0 }
    }
    try:
        FANUCPoseModel.parse_poses_from_data(invalid_data_bad_type)
    except ValueError as e:
        print(f"   ✅ 의도된 예외 발생(ValueError): {e}") #
    except Exception as e:
        print(f"   ❌ 잘못된 예외 발생: {type(e).__name__}: {e}")
        
    # 5. get_pose 실패 테스트
    print("\n5️⃣  get_pose() 실패 테스트 (없는 ID):")
    try:
        FANUCPoseModel.get_pose(poses, "Macro_99")
    except KeyError as e:
        print(f"   ✅ 의도된 예외 발생(KeyError): {e}") #
    except Exception as e:
        print(f"   ❌ 잘못된 예외 발생: {type(e).__name__}: {e}")

    # 6. to_struct 테스트 (Struct Packing 검증)
    print("\n6️⃣  to_struct() 구조체 패킹 테스트:")
    
    # 더미 데이터 생성
    prev_pos = FANUCPose(x=0, y=0, z=0, w=0, p=0, r=0, f=0)
    target_pos = FANUCPose(x=10.0, y=-5.0, z=0, w=0, p=0, r=0, f=100.0) # x=10(양이동), y=-5(음이동), feed_rate=100
    
    signals = {
        'IMSP': True, 'Hold': True, 'SFSP': True, 'Enable': True,  # UI_Byte1 = 1|2|4|128 = 135 (0x87)
        'RSR2': True,                                             # UI_Byte2 = 2 (0x02)
        'DI43': True                                              # UI_Byte3 (Signal part) = 4 (0x04)
    }

    try:
        struct_data = target_pos.to_struct(prev_pos, signals)
        
        print(f"   [UI_Byte1] Expected: 0x87, Actual: {hex(struct_data.UI_Byte1)}")
        print(f"   [UI_Byte2] Expected: 0x02, Actual: {hex(struct_data.UI_Byte2)}")
        
        # Feed Rate: 100.0 * 1000 = 100000 (0x0186A0)
        # Feed_High (0x01) -> UI_Byte3 상위 4비트에 들어감
        # UI_Byte3 = (0x01 << 4) | 0x04 (Signal) = 0x14
        print(f"   [UI_Byte3] Expected: 0x14, Actual: {hex(struct_data.UI_Byte3)}")
        print(f"   [Feed_Low] Expected: 0x86A0, Actual: {hex(struct_data.Feed_Low)}")
        
        # X Axis: 10.0 * 1000 = 10000 (0x2710)
        # X_High = 0x00, X_Low = 0x2710
        print(f"   [X_Axis]   High: {hex(struct_data.X_High)}, Low: {hex(struct_data.X_Low)}")

        # Y Axis: -5.0 * 1000 = -5000 -> abs -> 5000 (0x1388)
        # Y가 음수이므로 CheckBits의 해당 비트(1번째, index=1)가 1이어야 함 -> 0x02
        print(f"   [Y_Axis]   High: {hex(struct_data.Y_High)}, Low: {hex(struct_data.Y_Low)}")
        print(f"   [CheckBits] Expected (Y=neg): 0x02, Actual: {hex(struct_data.Check_Bits)}")

        assert struct_data.UI_Byte1 == 0x87
        assert struct_data.UI_Byte3 == 0x14
        assert struct_data.Check_Bits == 0x02
        print("   ✅ 구조체 패킹 테스트 성공")

    except Exception as e:
        print(f"   ❌ 구조체 생성 실패: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)