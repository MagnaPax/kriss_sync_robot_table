# communication/mock_plc.py
import time
import pyads
from utils.logger import get_logger

class MockConnection:
    """
    가상 PLC 연결 객체 (개발용)
    실제 하드웨어 없이 로직을 테스트하기 위해 pyads.Connection을 흉내냄
    """
    def __init__(self, ams_net_id, port):
        self.ams_net_id = ams_net_id
        self.port = port
        self.logger = get_logger(__name__)
        self._is_open = False

    def open(self):
        self._is_open = True
        self.logger.info(f"[MOCK] 가상 PLC 연결 열림 ({self.ams_net_id}:{self.port})")

    def close(self):
        self._is_open = False
        self.logger.info("[MOCK] 가상 PLC 연결 닫힘")

    def read_state(self):
        if not self._is_open:
            raise pyads.ADSError(text="Port not open")
        # 정상 상태(RUN) 반환 흉내
        return (pyads.ADSSTATE_RUN, 0)

    def read_by_name(self, name, plc_type):
        # 읽기 요청이 오면 무조건 0(False) 또는 1(True) 반환
        # Busy 신호 대기 로직 등을 테스트하려면 여기서 조작 가능
        # 예: Busy 신호는 처음엔 False였다가 나중에 True가 되는 식 (고급 모킹)
        return 0

    def write_by_name(self, name, value, plc_type):
        self.logger.debug(f"[MOCK] Write: {name} = {value}")
