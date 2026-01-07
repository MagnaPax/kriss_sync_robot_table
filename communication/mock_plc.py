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

    def open(self):
        self._is_open = True
        self.logger.info(f"[MOCK] 가상 PLC 연결 열림 ({self.ams_net_id}:{self.port})")

    def close(self):
        self._is_open = False
        self.logger.info("[MOCK] 가상 PLC 연결 닫힘")

    def read_state(self):
        if not self._is_open:
            raise pyads.ADSError(text="Port not open")
        return (pyads.ADSSTATE_RUN, 0)

    # ==========================================================
    # Read / Write
    # ==========================================================
    def read_by_name(self, name: str, plc_type: Any) -> Any:
        # 서보 피드백 더미 값 (IntegratedExecutor 초기화 통과용)
        if "Act_pos" in name: return 0.0
        if "Act_vel" in name: return 0.0
        if "bError" in name: return False
        
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
