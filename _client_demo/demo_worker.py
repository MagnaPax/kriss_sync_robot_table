# demo_worker.py

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from fanuc_logic import FanucController
from _client_demo.demo_plc_mock_model import MockFanucController


# 타입 힌트를 위해 Union 사용
ControllerType = FanucController | MockFanucController


# --- 백그라운드 워커 (UI 멈춤 방지) ---
class ConnectionWorker(QObject):
    """'PLC 연결을 담당하는 워커"""
    connection_result = pyqtSignal(bool, str) # (성공 여부, 상태 메시지)
    finished = pyqtSignal()

    def __init__(self, controller: ControllerType):
        super().__init__()
        self.controller = controller

    @pyqtSlot()
    def run(self):
        try:
            # 컨트롤러의 connect_plc 메서드 호출 (실제/Mock 공통)
            success, status_msg = self.controller.connect_plc()
            self.connection_result.emit(success, status_msg)
        finally:
            # 성공/실패 여부와 관계없이 항상 finished 시그널을 방출하여 스레드 정리
            self.finished.emit()

class CommandWorker(QObject):
    """좌표 전송을 담당하는 워커 (라이브/데모 모드 공용)"""
    log_message = pyqtSignal(str)
    command_finished = pyqtSignal(str) # (결과 메시지)
    finished = pyqtSignal()

    def __init__(self, controller: ControllerType, coords: list):
        super().__init__()
        self.controller = controller
        self.coords = coords

    @pyqtSlot()
    def run(self):
        try:
            self.log_message.emit("좌표 전송 시작...(실제 PLC쓰기)")
            # 컨트롤러의 execute_command 메서드 호출 (실제든 Mock이든)
            success, status_msg = self.controller.execute_command(*self.coords)
            
            if not success:
                self.log_message.emit(f"전송 실패: {status_msg}")
            
            self.command_finished.emit(status_msg)
        finally:
            # 성공/실패 여부와 관계없이 항상 finished 시그널을 방출하여 스레드 정리
            self.finished.emit()
