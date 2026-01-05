# workers/heartbeat_worker.py
import time
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from communication.twincat_connector import TwinCATConnector

class HeartbeatWorker(QObject):
    """
    [백그라운드] 연결 상태 감시자 (Heartbeat)
    주기적으로 TwinCAT 연결이 살아있는지 확인하고, 끊기면 즉시 보고함
    """
    finished = pyqtSignal()
    connection_lost = pyqtSignal() # 연결 끊김 감지 시그널

    def __init__(self, connector: "TwinCATConnector", interval: float = 1.0):
        super().__init__()
        self.connector = connector
        self.interval = interval
        self._is_running = True

    @pyqtSlot()
    def run(self):
        """감시 루프 시작"""
        while self._is_running:
            try:
                # 연결 상태 확인 (Blocking 가능성 있음)
                is_alive = self.connector.check_connection()

                if not is_alive:
                    # 연결이 끊겼다면 시그널 보내고 루프 종료
                    self.connection_lost.emit()
                    break

                # 2초 대기 (sleep은 이 스레드만 멈추므로 UI에 영향 없음)
                time.sleep(self.interval)

            except Exception:
                # 체크 과정 자체 에러 시 끊김으로 간주
                self.connection_lost.emit()
                break

        try:
            self.finished.emit()
        except RuntimeError:
            pass

    def stop(self):
        """감시 중지 요청"""
        self._is_running = False
