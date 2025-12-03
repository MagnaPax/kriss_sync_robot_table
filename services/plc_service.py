# services/plc_service.py
import time
from PyQt6.QtCore import QObject, QTimer, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.event_bus import EVENT_BUS
from communication.twincat_connector import TwinCATConnector
from communication.twincat_commander import TwinCATCommander
from utils.logger import get_logger

class PLCService(QObject):
    """
    PLC 통신 총괄 관리자 (Service Layer)
    
    역할:
    1. Model(Connector, Commander) 소유 및 관리
    2. Heartbeat(연결 상태) 주기적 체크
    3. 앱 종료 시 안전하게 연결 해제
    """
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)
        
        # 서비스가 Model을 소유 - 연결과 명령 담당 객체 생성
        self.connector = TwinCATConnector()
        self.commander = TwinCATCommander(self.connector)
        
        # ---------------------------------------------------------
        # 연결 상태 정기적으로 확인 (Heartbeat)
        # ---------------------------------------------------------
        self._heartbeat_timer = QTimer()
        self._heartbeat_timer.setInterval(2000) # 2초마다
        self._heartbeat_timer.timeout.connect(self._check_heartbeat)

        # ---------------------------------------------------------
        # 앱 종료 시 연결 끊기
        # ---------------------------------------------------------
        # AppEngine이 종료 신호를 보내면 -> disconnect_plc 메서드가 자동 실행됨
        EVENT_BUS.app_shutting_down.connect(self.disconnect_plc)


    def connect_plc(self):
        """연결 요청"""
        try:
            # Model에게 연결 시킴
            self.connector.connect()
            
            # 성공하면 Heartbeat 타이머 시작
            self._heartbeat_timer.start()
            
            EVENT_BUS.connection_status_changed.emit(True)
            EVENT_BUS.ui_log_message.emit("PLC 연결 성공 및 모니터링 시작", "INFO")
            
        except Exception as e:
            EVENT_BUS.ui_log_message.emit(f"PLC 연결 실패: {e}", "ERROR")


    @pyqtSlot()
    def disconnect_plc(self):
        """연결 해제 (앱 종료 시 or 수동 끊기)"""
        # 타이머 먼저 정지 (죽은 연결을 체크하지 않도록)
        self._heartbeat_timer.stop()
        
        if self.connector.is_connected:
            self.connector.disconnect()
            EVENT_BUS.connection_status_changed.emit(False)
            EVENT_BUS.ui_log_message.emit("PLC 연결이 안전하게 해제되었습니다.", "INFO")



    def connect_with_retry(self, ui_callback=None) -> bool:
        """
        재시도 로직을 포함한 연결 시도(블록킹 + UI 업데이트)

        인자:
            ui_callback(함수) : UI 진행률/메세지 업데이트용 함수
        """
        self._heartbeat_timer.stop() # 재연결 중에는 연결확인 중지

        max_retries = 3
        
        for i in range(1, max_retries + 1):

            # 진행률 계산 (40%에서 시작하여 15%씩 증가) - dll 파일 읽기가 0% ~ 30% 차지
            progress = 40 + (i * 15)

            try:
                # UI 업데이트
                msg = f"TwinCAT 연결 시도 중... ({i}/{max_retries})"
                if ui_callback:
                    ui_callback(msg, progress)
                QApplication.processEvents()    # UI 갱신

                # 연결 시도
                self.connector.connect()

                # 성공 처리
                success_msg = "TwinCAT 연결 성공! 시스템을 시작합니다."
                if ui_callback:
                    ui_callback(success_msg, 100)

                EVENT_BUS.system_info.emit("TwinCAT 연결 성공")
                EVENT_BUS.connection_status_changed.emit(True)
                EVENT_BUS.ui_log_message.emit(success_msg, "INFO")

                # 연결 확인 다시 시작
                self._heartbeat_timer.start()
                
                QApplication.processEvents()
                time.sleep(0.5)

                return True

            except Exception as e:
                EVENT_BUS.ui_log_message.emit(f"TwinCAT 접속 시도({i}) 실패: {e}", "ERROR")

                if i < max_retries:
                    if ui_callback:
                        ui_callback(f"접속 실패. 잠시 후 재시도...", progress)

                    # 대기(UI Freezing 방지)
                    end_time = time.time() + 1.0
                    while time.time() < end_time:
                        QApplication.processEvents()
                else:
                    EVENT_BUS.ui_log_message.emit("TwinCAT 연결 실패", "CRITICAL")
                    return False

        return False



    def _check_heartbeat(self):
        """2초마다 실행되어 연결 상태 확인"""

        # Model의 check_connection 호출
        is_alive = self.connector.check_connection()
        
        if not is_alive:
            self._heartbeat_timer.stop()


            # --- 비상 상황 알림 --- #

            # 통신 연결 상태 변경 시그널 emit
            EVENT_BUS.connection_status_changed.emit(False)
            EVENT_BUS.ui_log_message.emit("⚠️ TwinCAT 연결 끊김 감지!", "ERROR")

            # 시스템 에러 발생 시그널 emit
            EVENT_BUS.system_error.emit("TwinCAT_DISCONNECTED")
