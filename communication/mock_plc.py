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
        
        # Servo Data (1: Revolution, 2: Rotation, 3: Turntable)
        self._servo_pos = {1: 0.0, 2: 0.0, 3: 0.0}
        self._servo_vel = {1: 10.0, 2: 100.0, 3: 300.0} # 속도 차이 확연하게 (10, 100, 300)
        
        # for sine wave animation
        self._sim_time = 0.0

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

        # 기본값
        return 0

    def write_by_name(self, name: str, value: Any, plc_type: Any):
        # self.logger.debug(f"[MOCK] Write: {name} = {value}")
        
        # [Simulation] 로봇 동작 트리거 감지
        # 1. DI44 (Trigger) Rising Edge
        if "DI44" in name and value is True:
            self._simulate_robot_motion("DI44 Trigger")
            
        # 2. _UI1Struct 전송 시 RSR2 (Start) 또는 DI44 (Trigger) 체크
        if "Robot1._UI1" in name:
            triggered = False
            
            # (A) DI44 Check (Priority 1: Trigger)
            if hasattr(value, 'UI_Byte3'):
                ui3 = getattr(value, 'UI_Byte3', 0)
                if ui3 & 0x08: # DI44 (1 << 3)
                    self._simulate_robot_motion("DI44 Trigger (Struct)")
                    triggered = True
            
            # (B) RSR2 Check (Priority 2: Output Start - Rising Edge Only)
            if hasattr(value, 'UI_Byte2'):
                ui2 = getattr(value, 'UI_Byte2', 0)
                is_rsr2_high = bool(ui2 & 0x02) # RSR2 (1 << 1)
                
                # Rising Edge 감지: 이전에 Low였는데 지금 High일 때만 Trigger
                if is_rsr2_high and not self._is_rsr2_active:
                    if not triggered: # DI44랑 겹치면 DI44가 우선
                        self._simulate_robot_motion("RSR2 Start (Struct)")
                
                # 상태 업데이트
                self._is_rsr2_active = is_rsr2_high
            else:
                self._is_rsr2_active = False

    def write_list_by_name(self, data_map: Dict[str, Any]):
        """배치 쓰기 모킹"""
        # self.logger.debug(f"[MOCK] Batch Write: {len(data_map)} items")
        # 여기서도 트리거가 있는지 확인 가능하지만, 
        # 현재 IntegratedExecutor는 Servo만 Batch로 쏘고 Robot은 개별 Write함.
        pass

    def write_control(self, ads_state, device_state, data, plc_type):
        """TwinCAT 상태 제어 모킹 (ensure_run_mode 지원)"""
        self.logger.info(f"[MOCK] write_control 호출됨: State={ads_state}")
        # 아무것도 안 함 (이미 read_state에서 항상 RUN을 리턴하므로)

    # ==========================================================
    # Notification (Callback) Support
    # ==========================================================
    def add_device_notification(self, loop_name: str, attr: Any, callback: Callable) -> int:
        with self._lock:
            self._callback_counter += 1
            handle = self._callback_counter
            self._callbacks[handle] = (callback, loop_name)
            self.logger.info(f"[MOCK] Notification 등록: {loop_name} (Handle: {handle})")
            return handle

    def del_device_notification(self, handle: int):
        with self._lock:
            if handle in self._callbacks:
                del self._callbacks[handle]
                # self.logger.debug(f"[MOCK] Notification 해제: {handle}")

    # ==========================================================
    # Simulation Logic
    # ==========================================================
    def _simulate_robot_motion(self, trigger_source: str):
        """
        로봇이 움직이는 상황을 시뮬레이션
        Trigger -> (Wait) -> Calc Req(DO45) -> (Wait) -> Motion Done(DO46)
        """
        self.logger.info(f"[MOCK-SIM] 로봇 동작 시작 ({trigger_source})")
        
        # 비동기 지연 실행 (타이머)
        # 1. 0.5초 후: Calc Req (DO45) ON -> "다음 데이터 계산해줘"
        t1 = threading.Timer(0.5, self._fire_notification, args=("DO45", True))
        t1.start()
        
        # 2. 1.5초 후: Motion Done (DO46) ON -> "이번 동작 끝났어"
        # 2. 1.5초 후: Motion Done (DO46) ON -> "이번 동작 끝났어"
        t2 = threading.Timer(1.5, self._fire_notification, args=("DO46", True))
        t2.start()

        # 3. 1.7초 후: Turntable Done (bDone3) ON -> "턴테이블도 끝났어" (동기 검증용)
        # 로봇보다 약간 늦게 도착하는 상황 시뮬레이션
        t3 = threading.Timer(1.7, self._fire_notification, args=("bDone3", True))
        t3.start()

    def _fire_notification(self, signal_keyword: str, value: Any):
        """저장된 콜백 중 해당 신호를 구독하는 콜백 실행"""
        with self._lock:
            # 복사본으로 순회 (Thread Safe)
            targets = list(self._callbacks.items())
            
        for handle, (callback, loop_name) in targets:
            # loop_name(심볼)에 signal_keyword(예: DO45)가 포함되어 있으면 콜백 호출
            if signal_keyword in loop_name:
                try:
                    # pyads 콜백 서명: (handle, name, datetime, value)
                    # 하지만 Adapter에서는 (notification, data) 형태를 기대할 수 있음
                    # fanuc_adapter.py wrapper: callback(notification, data)
                    # 여기서는 그냥 단순하게 호출
                    import datetime
                    timestamp = datetime.datetime.now()
                    
                    # 로깅
                    # self.logger.debug(f"[MOCK-SIM] Fire {signal_keyword} -> Handle {handle}")
                    
                    # 실제 pyads 콜백은 (handle, timestamp, value) 등을 줄 수 있음.
                    # Adapter 구현: def _cb(n, d): ...
                    # Mock에서는 편의상 (handle, value) 전달
                    callback(handle, value)
                except Exception as e:
                    self.logger.error(f"[MOCK] Callback Error: {e}")

    def _simulation_loop(self):
        """백그라운드에서 센서 데이터 변경 (애니메이션 효과)"""
        import math
        while self._sim_running:
            self._sim_time += 0.1
            t = self._sim_time
            
            # 1. 로봇 좌표 (원 그리기 운동)
            # Center(300, 0), Radius 100
            self._robot_data['X'] = 300.0 + 100.0 * math.cos(t * 0.5)
            self._robot_data['Y'] = 100.0 * math.sin(t * 0.5)
            self._robot_data['Z'] = 150.0 + 50.0 * math.sin(t * 1.0) # 위아래 움직임
            
            # W, P, R 은 대충 움직임
            self._robot_data['W'] = 180.0 + 10.0 * math.sin(t * 0.3) # 180도 부근에서 흔들기
            self._robot_data['P'] = 10.0 * math.cos(t * 0.7)         # 0도 부근에서 흔들기
            self._robot_data['R'] = (t * 10) % 360 - 180
            
            # 2. 서보 모터 (계속 회전)
            # Axis 3 (Turntable): 0~360 반복
            self._servo_pos[3] = (self._servo_pos[3] + self._servo_vel[3] * 0.1) % 360.0
            
            # Axis 1 (Revolution), 2 (Rotation): 계속 증가
            self._servo_pos[1] = (self._servo_pos[1] + self._servo_vel[1] * 0.1) % 360.0
            self._servo_pos[2] = (self._servo_pos[2] + self._servo_vel[2] * 0.1) % 360.0
            
            time.sleep(0.1) # 10Hz 업데이트
