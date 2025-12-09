# services/plc_service.py
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, QTimer, pyqtSlot, QThread, Qt, QMetaObject

from core.event_bus import EVENT_BUS
from workers.plc_worker import PLCWorker
from models.position_model import Position
from communication.twincat_connector import TwinCATConnector
from communication.twincat_commander import TwinCATCommander



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
        
        # 서비스가 Model을 소유 - 연결과 명령 담당 객체 생성
        self.connector = TwinCATConnector()
        self.commander = TwinCATCommander(self.connector)


        # --- 비동기 작업용 스레드/워커 변수 --- #
        # 새로운 사무실(QThread) '공간 확보'
        self._thread: QThread | None = None
        # 비서(Worker) 직군 '정원 확보'
        self._worker: PLCWorker | None = None


        # --- 연결 상태 정기적으로 확인 (Heartbeat) --- #
        self._heartbeat_timer = QTimer()
        self._heartbeat_timer.setInterval(2000) # 2초마다
        self._heartbeat_timer.timeout.connect(self._check_heartbeat)


        # --- 앱 종료 시 연결 끊기 --- #
        # AppEngine이 종료 신호를 보내면 -> disconnect_plc 메서드가 자동 실행됨
        EVENT_BUS.app_shutting_down.connect(self.disconnect_plc)



    # ==========================================================
    # 연결 관련 메서드
    # ==========================================================

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



    # ==========================================================
    # [비동기] 로봇 제어 명령 (Worker 사용)
    # ==========================================================
    def start_process(self):
        self._start_worker('START', log_msg="프로세스 시작 요청...")


    def stop_process(self):
        # 진행 중인 워커가 있다면 중단 요청
        if self._thread and self._thread.isRunning():
            self._thread.requestInterruption()

        self._start_worker('STOP', log_msg="프로세스 중지 요청...")


    def move_robot(self, position:Position):
        """좌표 이동 요청"""

        try:
            # 객체 -> 딕셔너리 변환
            # Worker는 내부적으로 딕셔너리 리스트를 처리하도록 설계되어 있기 때문
            coords_dict = position.to_unified_dict()

            # 메타 데이터 추가(빼도 됨)
            coords_dict['name'] = 'Manual_Position_Obj'

            # Worker 규격(List[Dict])에 맞춰 포장
            sequence_data = [coords_dict]

            # Worker 호출
            self._start_worker('MOVE', data=sequence_data, log_msg=f"단일 명령 이동: {position}")

        except Exception as e:
            EVENT_BUS.ui_log_message.emit(f"좌표 이동 실패: {e}", "ERROR")


    def _start_worker(self, command: str, data=None, log_msg: str = ""):
        """비동기 워커 스레드 생성 및 실행 (공통 로직)"""

        if self._thread and self._thread.isRunning():
            if command == 'STOP':
                self._thread.requestInterruption()  # 강제 중단 요청
            else:
                EVENT_BUS.ui_log_message.emit("이전 작업이 아직 진행중입니다", "WARNING")
                return # 이전 작업이 있다면 중복 실행 방지

        if log_msg:
            EVENT_BUS.ui_log_message.emit(log_msg, "INFO")

        # 사무실 계약
        self._thread = QThread()

        # 비서(Worker) 채용
        self._worker = PLCWorker(self.connector, self.commander, command, data)

        # 비서를 새 사무실로 전근 발령 - moveToThread() : 스레드 소속 변경
        self._worker.moveToThread(self._thread)


        # 비서의 전화보고(emit)를 받고 어떻게 처리(Slot)할지 미리 정해놓기(connect)
        self._worker.result.connect(self._handle_worker_result)
        self._worker.finished.connect(self._cleanup)

        # --- 사무실(Thread)에서 벌어질 이벤트 예약(connect) ---
        # 사무실 문 열리면 비서에게 “일 시작해라” 지시
        self._thread.started.connect(self._worker.run)
        # 사무실이 문 닫히면 → 사무실 정리하고 폐기하도록 예약
        self._thread.finished.connect(self._thread.deleteLater)


        # 사무실 오픈(스레드 시작)
        # 사무실 문을 열고 내부 이벤트 루프를 가동하는 것
        self._thread.start()



    # ==========================================================
    # [슬롯] Worker 시그널에 대한 처리
    # ==========================================================
    @pyqtSlot(bool, str)
    def _handle_worker_result(self, success: bool, msg: str):
        """워커 실행 결과 처리"""
        level = "INFO" if success else "ERROR"
        EVENT_BUS.ui_log_message.emit(msg, level)

    @pyqtSlot()
    def _cleanup(self):
        """
        실행 중인 스레드(사무실)와 워커(비서)를
        우아하게 종료하고 메모리 누수 없이 안전하게 폐기하는 함수
        """
        if self._thread and self._thread.isRunning():
            self._thread.quit()     # Thread의 이벤트 루프 종료 요청 - 남아 있는 이벤트 처리 후 종료
            self._thread.wait(2000) # 사무실이 안전하게 문 닫을 때까지 2초동안 기다림

        if self._worker:
            self._worker.deleteLater()  # 비서 정리 → Qt의 메모리 관리 시스템에 맡겨서 안전하게 폐기
            self._worker = None         # Python 레벨에서도 비서 레퍼런스 해제(메모리 누수 방지)
