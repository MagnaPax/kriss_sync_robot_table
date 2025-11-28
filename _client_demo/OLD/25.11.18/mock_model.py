# mock_model.py
import time
from fanuc_logger import logger
# from utils.logger import Logger
# logger = Logger().logger


# --- Mock(가짜) PLC 객체 ---
class MockFanucController:
    """
    '데모 모드'에서 사용할 pyads.Connection의 가짜(Mock) 객체.
    실제 PLC가 없어도 UI가 작동하는지 테스트하기 위해
    """
    def __init__(self):
        self.is_connected = False
        self.log_messages = []
        logger.info("[MOCK] 가짜 FanucController 객체 생성") #

    def connect_plc(self) -> tuple[bool, str]:
        self.log("[MOCK] PLC 연결 시도... (네트워크 딜레이 1초 시뮬레이션)") #
        time.sleep(1.0)
        self.is_connected = True
        return True, "데모 모드: 가짜 PLC 연결 성공"

    def disconnect_plc(self):
        self.is_connected = False
        logger.info("[MOCK] PLC 연결 종료.") #

    def execute_command(self, x: float, y: float, z: float, w: float, p: float, r: float, f: float) -> tuple[bool, str]:

        if not self.is_connected:
            return False, "데모 모드: PLC가 연결되지 않았습니다."

        self.log("[MOCK] RSR 신호 OFF") #
        self.log("좌표 전송 시작...") #

        # 제어 로직이 호출되었는지 확인하기 위해 로그에 좌표값 포함
        coords_str = f"[X:{x}, Y:{y}, Z:{z}, W:{w}, P:{p}, R:{r}, F:{f}]"
        self.log(f"[MOCK] RSR 신호 OFF") #
        self.log(f"[MOCK] 좌표 쓰기: {coords_str}") #
        self.log(f"[MOCK] Feed 쓰기") #
        self.log(f"[MOCK] RSR 신호 ON") #

        time.sleep(0.5) # fanuc_logic과 동일한 sleep

        return True, f"데모 모드: 명령 전송 완료 {coords_str}"

    def log(self, msg):
        # 기존 print 대신 logger.info 사용
        logger.info(msg) #
        self.log_messages.append(msg)
