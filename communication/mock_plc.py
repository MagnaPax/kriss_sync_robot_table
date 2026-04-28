import threading
import time
import ctypes
from typing import Any, Callable, Dict
import pyads
from utils.logger import get_logger

class MockConnection:
    """
    가상 PLC 연결 객체 (개발용)
    IntegratedExecutor 및 FanucAdapter 테스트를 위해
    Notification(Callback)과 배치 쓰기를 지원하도록 리팩토링됨.
    """
    def __init__(self, ams_net_id: str, port: int):
        print(f"DEBUG: MockConnection initialized. Has add_device_notification? {hasattr(self, 'add_device_notification')}")
        self.ams_net_id = ams_net_id
        self.port = port
        self.logger = get_logger(__name__)
        self._is_open = False
        
        # Notification Callbacks: {handle: (callback, attr)}
        self._callbacks: Dict[int, tuple] = {}
        self._callback_counter = 0
        self._lock = threading.RLock()
        
        # [State] RSR2 신호 상태 추적 (Rising Edge 감지용)
        self._is_rsr2_active = False

        # [Simulation Data]
        self._sim_running = False
        self._sim_thread = None
        
        # Robot Pose (X, Y, Z, W, P, R)
        self._robot_data = {'X': 300.0, 'Y': 0.0, 'Z': 150.0, 'W': 180.0, 'P': 0.0, 'R': 0.0}
        self._robot_data = {'X': 0.1, 'Y': 0.1, 'Z': 0.1, 'W': 0.1, 'P': 0.1, 'R': 0.1}
        
        # Servo Data (1: Revolution, 2: Rotation, 3: Turntable)
        self._servo_pos = {1: 0.0, 2: 0.0, 3: 0.0}
        self._servo_vel = {1: 10.0, 2: 100.0, 3: 300.0} # 속도 차이 확연하게 (10, 100, 300)
        
        # for sine wave animation
        self._sim_time = 0.0

        # [Servo Simulation] Control States
        self._servo_mode: Dict[int, str] = {1: "IDLE", 2: "IDLE", 3: "IDLE"}
        self._servo_target_vel: Dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0}
        self._servo_target_pos: Dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0}

    @property
    def is_open(self) -> bool:
        return self._is_open

    def open(self):
        self._is_open = True
        self.logger.info(f"[MOCK] 가상 PLC 연결 열림 ({self.ams_net_id}:{self.port})")
        
        # 시뮬레이션 시작
        self._sim_running = True
        self._sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._sim_thread.start()

    def close(self):
        self._is_open = False
        self._sim_running = False
        if self._sim_thread:
            self._sim_thread.join(timeout=1.0)
        self.logger.info("[MOCK] 가상 PLC 연결 닫힘")

    def read_state(self):
        if not self._is_open:
            raise pyads.ADSError(text="Port not open")
        return (pyads.ADSSTATE_RUN, 0)

    # ==========================================================
    # Read / Write
    # ==========================================================
    def read_by_name(self, name: str, plc_type: Any) -> Any:
        # 1. 서보 피드백 (LREAL)
        # MAIN.Act_pos1, MAIN.Act_vel2 등
        if "Act_pos" in name:
            try:
                axis = int(name[-1]) # 마지막 글자가 숫자라고 가정 (1~3)
                return float(self._servo_pos.get(axis, 0.0))
            except:
                return 0.0
                
        if "Act_vel" in name:
            try:
                axis = int(name[-1])
                return float(self._servo_vel.get(axis, 0.0))
            except:
                return 0.0

        if "bError" in name: return False
        
        # 2. 로봇 피드백 (Bit-wise)
        # 예: "MAIN.Robot1._UO1.Xh0", "MAIN.Robot1._UO1.Xl15", "MAIN.Robot1._UO1.X_Check"
        if "MAIN.Robot1._UO1." in name:
            try:
                # 파싱: "Xh0" -> axis="X", part="h", bit="0"
                # "X_Check" -> axis="X", part="Check"
                
                suffix = name.split(".")[-1] # Xh0, Yl12, Z_Check
                axis = suffix[0] # X, Y, Z, W, P, R
                
                val = self._robot_data.get(axis, 0.0)
                int_val = int(abs(val * 1000)) # 스케일링
                
                if "_Check" in suffix:
                    return (val < 0) # 음수이면 True
                
                # h0..h7 or l0..l15
                part = suffix[1] # 'h' or 'l'
                bit_idx = int(suffix[2:]) # 0, 15, ...
                
                if part == 'h':
                    # 상위 8비트: 16~23비트 영역 (High Byte)
                    # 원본 로직: top_val |= (1 << i) ... raw_val = (top_val << 16) | low_val
                    # 즉, h0은 전체 24비트 중 16번째 비트
                    # int_val >> 16 의 bit_idx 번째 비트
                    byte_val = (int_val >> 16) & 0xFF
                    return bool((byte_val >> bit_idx) & 1)
                    
                elif part == 'l':
                    # 하위 16비트 (Low Word)
                    # l0은 0번째 비트
                    word_val = int_val & 0xFFFF
                    return bool((word_val >> bit_idx) & 1)
                    
            except Exception:
                pass

        if hasattr(self, '_gvl_state') and name in self._gvl_state:
            return self._gvl_state[name]

        # 기본값
        return 0

    # ==========================================================
    # Write by Name (PLC 명령 수신)
    # ==========================================================
    def get_symbol(self, name: str):
        class DummySymbol:
            def __init__(self):
                self.index_group = 0
                self.index_offset = 0
        return DummySymbol()

    def write(self, index_group: int, index_offset: int, data: Any, plc_type: Any = None):
        self.logger.debug(f"[MOCK] write(group={index_group}, offset={index_offset}, size={len(data) if isinstance(data, bytes) else '?'})")

    def write_list_by_name(self, data_map: Dict[str, Any]):
        """여러 변수를 한 번에 쓰기 (Batch Write)"""
        for name, value in data_map.items():
            self.write_by_name(name, value, None)

    def write_by_name(self, name: str, value: Any, plc_type: Any = None):
        if not hasattr(self, '_gvl_state'):
            self._gvl_state = {}
        self._gvl_state[name] = value

        # self.logger.debug(f"[MOCK] Write: {name} = {value}")
        
        # ---------------------------------------------------------------------
        # [Servo Simulation] 서보 제어 신호 가로채기
        # ---------------------------------------------------------------------
        if "MAIN." in name:
            # 1. 목표 속도 설정 (vel1, vel2, vel3)
            if "vel" in name and "Move" not in name and "Act" not in name:
                try:
                    axis = int(name[-1])
                    self._servo_target_vel[axis] = float(value)
                except: pass

            # 2. 목표 위치 설정 (pos1, pos2, pos3)
            elif "pos" in name and "Read" not in name and "Act" not in name:
                try:
                    axis = int(name[-1])
                    self._servo_target_pos[axis] = float(value)
                except: pass

            # 3. 이동 명령 - 속도 모드 (bMoveVel1, 2, 3)
            elif "bMoveVel" in name and value is True:
                try:
                    axis = int(name[-1])
                    self._servo_mode[axis] = "VELOCITY"
                    # self.logger.debug(f"[MOCK] Axis {axis} Velocity Move Start -> Target {self._servo_target_vel[axis]}")
                except: pass

            # 4. 이동 명령 - 위치 모드 (bMoveAbs1, 2, 3)
            elif "bMoveAbs" in name and value is True:
                try:
                    axis = int(name[-1])
                    self._servo_mode[axis] = "POSITION"
                    # self.logger.debug(f"[MOCK] Axis {axis} Position Move Start -> Target {self._servo_target_pos[axis]}")
                except: pass

            # 5. 정지 명령 (bStop1, 2, 3)
            elif "bStop" in name and value is True:
                try:
                    axis = int(name[-1])
                    self._servo_mode[axis] = "IDLE"
                    self._servo_target_vel[axis] = 0.0
                except: pass

            # 6. 원점 복귀 (bHome1, 2, 3)
            elif "bHome" in name and value is True:
                try:
                    axis = int(name[-1])
                    self._servo_mode[axis] = "HOMING"
                    # 3초 뒤에 원점 완료 처리
                    threading.Timer(3.0, self._finish_homing, args=(axis,)).start()
                except: pass

        # ---------------------------------------------------------------------
        # [MOCK] 개발용 강제 값 주입 (Backdoor)
        # ---------------------------------------------------------------------
        if "MOCK.Robot." in name:
            # 예: MOCK.Robot.X, MOCK.Robot.R 등
            axis = name.split(".")[-1] # X, Y, Z, W, P, R
            if axis in self._robot_data:
                self._robot_data[axis] = float(value)
                self.logger.info(f"[MOCK-DEV] 로봇 좌표 강제 설정: {axis} = {value}")

        if "MOCK.Servo." in name:
            # 예: MOCK.Servo.1, MOCK.Servo.2
            try:
                axis = int(name.split(".")[-1])
                if axis in self._servo_pos:
                    self._servo_pos[axis] = float(value)
                    self.logger.info(f"[MOCK-DEV] 서보 좌표 강제 설정: Axis {axis} = {value}")
            except: pass

        # ---------------------------------------------------------------------
        # [Robot Simulation] 로봇 동작 트리거 감지
        # ---------------------------------------------------------------------
        # 1. DI44 (Trigger) Rising Edge
        if "DI44" in name and value is True:
            self._simulate_robot_motion("DI44 Trigger")
            
        # 2. _UI1Struct 전송 시 RSR2 (Start) 또는 DI44 (Trigger) 체크
        if "Robot1._UI1" in name:
            triggered = False
            packet = value # FanucCommandPacket
            
            # (A) DI44 Check (Priority 1: Trigger)
            if hasattr(packet, 'UI_Byte3'):
                ui3 = getattr(packet, 'UI_Byte3', 0)
                if ui3 & 0x08: # DI44 (1 << 3)
                    self._simulate_robot_motion("DI44 Trigger (Struct)", move_packet=packet)
                    triggered = True
            
            # (B) RSR2 Check (Priority 2: Output Start - Rising Edge Only)
            if hasattr(packet, 'UI_Byte2'):
                ui2 = getattr(packet, 'UI_Byte2', 0)
                is_rsr2_high = bool(ui2 & 0x02) # RSR2 (1 << 1)
                
                # Rising Edge 감지: 이전에 Low였는데 지금 High일 때만 Trigger
                if is_rsr2_high and not self._is_rsr2_active:
                    if not triggered: # DI44랑 겹치면 DI44가 우선
                        self._simulate_robot_motion("RSR2 Start (Struct)", move_packet=packet)
                
                # 상태 업데이트
                self._is_rsr2_active = is_rsr2_high
            else:
                self._is_rsr2_active = False

    def write_control(self, ads_state, device_state, data, plc_type):
        """TwinCAT 상태 제어 모킹 (ensure_run_mode 지원)"""
        self.logger.info(f"[MOCK] write_control 호출됨: State={ads_state}")
        # 아무것도 안 함 (이미 read_state에서 항상 RUN을 리턴하므로)

    # ==========================================================
    # Notification (Callback) Support
    # ==========================================================
    def add_device_notification(self, loop_name: str, attr: Any, callback: Callable, user_handle: int = 0) -> int:
        with self._lock:
            self._callback_counter += 1
            handle = self._callback_counter
            self._callbacks[handle] = (callback, loop_name)
            self.logger.info(f"[MOCK] Notification 등록: {loop_name} (Handle: {handle}, UserHandle: {user_handle})")
            return handle

    def del_device_notification(self, handle: int, user_handle: int = 0):
        with self._lock:
            if handle in self._callbacks:
                del self._callbacks[handle]
                # self.logger.debug(f"[MOCK] Notification 해제: {handle}")

    def _fire_notification(self, name_part: str, value: Any):
        """
        [내부용] 시뮬레이션 중 값이 바뀌었음을 알리고 콜백 호출
        name_part: 예) "DO45", "DO46" 등 감지할 이름의 일부
        value: 변경된 값
        """
        # 등록된 모든 콜백을 확인
        with self._lock:
            # {handle: (callback, loop_name)}
            for handle, (cb, loop_name) in self._callbacks.items():
                # 만약 등록된 변수 이름(loop_name)에 지금 바뀐 이름(name_part)이 포함되어 있다면?
                if name_part in loop_name:
                    try:
                        # 콜백 호출 (handle, value) - execution_strategies.py에서
                        # 인자 개수에 따라 유연하게 처리하므로 이렇게 넘겨도 됨.
                        cb(handle, value) 
                    except Exception as e:
                        self.logger.error(f"[MOCK] Callback Error: {e}")

    def _finish_homing(self, axis):
        """원점 복귀 완료 처리"""
        self._servo_pos[axis] = 0.0
        self._servo_vel[axis] = 0.0
        self._servo_mode[axis] = "IDLE"
        # self.logger.debug(f"[MOCK] Axis {axis} Homing Complete")

    # ==========================================================
    # Simulation Logic
    # ==========================================================
    def _simulate_robot_motion(self, trigger_source: str, move_packet=None):
        """
        로봇이 움직이는 상황을 시뮬레이션
        Trigger -> (Wait) -> Calc Req(DO45) -> (Wait) -> Motion Done(DO46)
        """
        self.logger.info(f"[MOCK-SIM] 로봇 동작 시작 ({trigger_source})")

        # [MOCK] 실제 좌표 이동 시뮬레이션
        if move_packet:
            axis_names = ['X', 'Y', 'Z', 'W', 'P', 'R']
            for i, axis in enumerate(axis_names):
                high = getattr(move_packet, f"{axis}_High", 0)
                low = getattr(move_packet, f"{axis}_Low", 0)
                
                # 값 복원 (High * 65536 + Low) / 1000
                raw_val = (high << 16) | low
                delta_val = raw_val / 1000.0
                
                # 음수 체크 (Check_Bits 해당 비트가 1이면 음수)
                if (move_packet.Check_Bits >> i) & 1:
                    delta_val = -delta_val
                
                # 현재 위치에 델타 적용
                self._robot_data[axis] += delta_val
                self.logger.debug(f"[MOCK-SIM] {axis} 축 이동: Delta({delta_val}) -> NewPos({self._robot_data[axis]})")

        # [핵심 수정] 기존 신호를 일단 끈다 (Rising Edge 준비)
        self._fire_notification("DO45", False)
        self._fire_notification("DO46", False)
        
        # 비동기 지연 실행 (타이머)
        # 1. 0.5초 후: Calc Req (DO45) ON -> "다음 데이터 계산해줘"
        t1 = threading.Timer(0.5, self._fire_notification, args=("DO45", True))
        t1.start()
        
        # 2. 1.5초 후: Motion Done (DO46) ON -> "이번 동작 끝났어"
        #    이로써 0 -> 1 변화가 확실해짐
        t2 = threading.Timer(1.5, self._fire_notification, args=("DO46", True))
        t2.start()

        # 3. 1.7초 후: Turntable Done (bDone3) ON -> "턴테이블도 끝났어" (동기 검증용)
        # 로봇보다 약간 늦게 도착하는 상황 시뮬레이션
        t3 = threading.Timer(1.7, self._fire_notification, args=("bDone3", True))
        t3.start()

    def _simulation_loop(self):
        """백그라운드에서 센서 데이터 변경 (애니메이션 효과)"""
        import math
        while self._sim_running:
            self._sim_time += 0.1
            dt = 0.1
            
            # [Servo Simulation] 물리 엔진 모방
            for axis in [1, 2, 3]:
                mode = self._servo_mode.get(axis, "IDLE")
                current_pos = self._servo_pos.get(axis, 0.0)
                current_vel = self._servo_vel.get(axis, 0.0)
                
                target_vel = self._servo_target_vel.get(axis, 0.0)
                target_pos = self._servo_target_pos.get(axis, 0.0)

                if mode == "VELOCITY":
                    # 속도 모드: 목표 속도까지 서서히 가속
                    # 간단하게: 
                    new_vel = target_vel # 가속도 무시하고 즉시 도달
                    new_pos = current_pos + new_vel * dt
                    
                    self._servo_vel[axis] = new_vel
                    self._servo_pos[axis] = new_pos
                    
                elif mode == "POSITION":
                    # 위치 모드: 목표 위치로 이동
                    dist = target_pos - current_pos
                    step = target_vel * dt
                    
                    if abs(dist) <= step:
                        # 도착
                        new_pos = target_pos
                        new_vel = 0.0
                    else:
                        # 이동 중
                        direction = 1.0 if dist > 0 else -1.0
                        new_vel = target_vel * direction
                        new_pos = current_pos + new_vel * dt
                        
                    self._servo_vel[axis] = new_vel
                    self._servo_pos[axis] = new_pos
                    
                elif mode == "HOMING":
                    # 호밍 중에는 속도만 약간 줌
                    self._servo_vel[axis] = 10.0
                
                else:
                    # IDLE: 정지
                    self._servo_vel[axis] = 0.0

            # [Robot Simulation] 로봇 좌표 미세 변동 (연결 확인용 Live Data)
            # PoseMonitorWorker가 변화를 감지할 수 있도록 약간의 노이즈 추가
            import random
            if self._sim_time % 1.0 < 0.1: # 1초마다
                noise_axis = random.choice(['X', 'Y', 'Z'])
                self._robot_data[noise_axis] += random.choice([-0.001, 0.001])


            time.sleep(dt) # 10Hz 업데이트
