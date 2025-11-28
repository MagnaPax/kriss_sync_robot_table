# demo_plc_mock_model.py
import time
from _client_demo.demo_logger import logger

# --- Mock(가짜) PLC 객체 ---
class MockFanucController:
    """
    '데모 모드'에서 사용할 pyads.Connection의 가짜(Mock) 객체.
    실제 PLC가 없어도 UI가 작동하는지 테스트하기 위해
    """
    def __init__(self):
        self.is_connected = False
        self.log_messages = []
        logger.info("[MOCK] 가짜 FanucController 객체 생성")

    def connect_plc(self) -> tuple[bool, str]:
        self.log("[MOCK] PLC 연결 시도... (네트워크 딜레이 1초 시뮬레이션)")
        time.sleep(1.0)
        self.is_connected = True
        return True, "데모 모드: 가짜 PLC 연결 성공"

    def disconnect_plc(self):
        self.is_connected = False
        logger.info("[MOCK] PLC 연결 종료.")

    def execute_command(self, x: float, y: float, z: float, w: float, p: float, r: float, f: float) -> tuple[bool, str]:
        if not self.is_connected:
            return False, "데모 모드: PLC가 연결되지 않았습니다."

        # 제어 로직이 호출되었는지 확인하기 위해 로그에 좌표값 포함
        coords_str = f"[X:{x}, Y:{y}, Z:{z}, W:{w}, P:{p}, R:{r}, F:{f}]"
        self.log(f"[MOCK] 좌표 전송 시뮬레이션: {coords_str}")
        
        # 실제 로직과 비슷한 딜레이
        time.sleep(0.05) 

        return True, f"데모 모드: 명령 전송 완료"

    # ==========================================================
    # [추가됨] 로봇 제어 메서드 (인터페이스 맞추기용)
    # ==========================================================
    def start_process_loop(self) -> tuple[bool, str]:
        if not self.is_connected: return False, "연결 안 됨"
        self.log("[MOCK] 프로세스 시작 (RSR2 Pulse + DI181 ON)")
        time.sleep(0.2) # 딜레이 시뮬레이션
        return True, "[MOCK] 프로세스 시작 완료"

    def send_cycle_stop(self) -> tuple[bool, str]:
        if not self.is_connected: return False, "연결 안 됨"
        self.log("[MOCK] 일시 정지 (Cycle Stop Pulse)")
        time.sleep(0.2)
        return True, "[MOCK] 일시 정지 완료"

    def send_cycle_start(self) -> tuple[bool, str]:
        if not self.is_connected: return False, "연결 안 됨"
        self.log("[MOCK] 다시 시작 (Cycle Start Pulse)")
        time.sleep(0.2)
        return True, "[MOCK] 다시 시작 완료"

    def set_loop_signal(self, is_active: bool) -> tuple[bool, str]:
        if not self.is_connected: return False, "연결 안 됨"
        state = "ON" if is_active else "OFF"
        self.log(f"[MOCK] 루프 신호(DI181) 설정: {state}")
        return True, f"[MOCK] 루프 신호 {state} 설정 완료"


    def log(self, msg):
        logger.info(msg)
        self.log_messages.append(msg)