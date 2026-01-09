# services/plc_service.py
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, QThread, pyqtSlot

from typing import Any, Dict, List, Optional, Callable
from core.event_bus import EVENT_BUS
from workers.plc_worker import PLCWorker
from models.fanuc_pose_model import FANUCPose
from communication.twincat_connector import TwinCATConnector
from communication.twincat_commander import TwinCATCommander
from communication.fanuc_adapter import FanucAdapter
from communication.servo_adapter import ServoAdapter
from workers.pose_monitor_worker import PoseMonitorWorker
from workers.heartbeat_worker import HeartbeatWorker



class PLCService(QObject):
    """
    하드웨어 관리소
        애플리케이션의 하드웨어 제어 계층에서 'Composition Root' 역할 수행
    """
    def __init__(self):
        super().__init__()
        self._log_prefix = f"[{self.__class__.__name__}]"
        
        # 장치 활성 상태 플래그 (통신 에러 시 자동 비활성화)
        self._is_robot_active = True
        self._is_servo_active = True
        
        # 1. 연결 담당 (지갑)
        self.connector = TwinCATConnector()

        # 2. 어댑터(손과 발) 생성 및 소유
        self.fanuc = FanucAdapter(self.connector)
        self.servo = ServoAdapter(self.connector)

        # 3. 커맨더(두뇌) 생성 후 어댑터 주입(Dependency Injection)
        self.commander = TwinCATCommander(self.connector, self.fanuc, self.servo)


        # --- 비동기 작업용 스레드/워커 변수 --- #
        # 새로운 사무실(QThread) '공간 확보'
        self._thread: QThread | None = None
        # 비서(Worker) 직군 '정원 확보'
        self._worker: PLCWorker | None = None

        # 긴급 명령(STOP 등) 전용 임시 스레드/워커
        # 이유: 원점 복귀 중일 때 STOP 명령을 보내려면, 원점 복귀 스레드(self._thread)와 별개로 
        #       동시에 실행되어야 하므로 별도의 스레드 변수가 필요함.
        self._emergency_thread: QThread | None = None
        self._emergency_worker: PLCWorker | None = None

        # 기기들의 현재 위치 모니터링 전용 스레드/워커
        self._pose_monitor_thread: QThread | None = None
        self._pose_monitor_worker: PoseMonitorWorker | None = None

        # TwinCAT 연결 감시용 스레드 변수
        self._heartbeat_thread: QThread | None = None
        self._heartbeat_worker: HeartbeatWorker | None = None


        # --- 연결 상태 변경 시 모니터링 시작/중지 --- #
        EVENT_BUS.conn.status_changed.connect(self._on_connectino_changed)


        # --- 앱 종료 시 연결 끊기 --- #
        # AppEngine이 종료 신호를 보내면 -> disconnect_plc 메서드가 자동 실행됨
        EVENT_BUS.system.shutting_down.connect(self.disconnect_plc)


    # ==========================================================
    # 연결 관련
    # ==========================================================
    @pyqtSlot() # type: ignore
    def disconnect_plc(self):
        """연결 해제 (앱 종료 시 or 수동 끊기)"""

        # 1. 모니터링 하는 애들 먼저 퇴근시킴
        self._stop_heartbeat_worker()
        self._stop_monitoring()

        # 2. 스레드 정리 및 대기
        self._cleanup(self._heartbeat_thread, self._heartbeat_worker, ['_heartbeat_thread', '_heartbeat_worker'])
        self._cleanup(self._pose_monitor_thread, self._pose_monitor_worker, ['_pose_monitor_thread', '_pose_monitor_worker'])

        # 3. 실제 연결 끊기
        if self.connector.is_connected:
            self.connector.disconnect()
            EVENT_BUS.conn.status_changed.emit(False)
            EVENT_BUS.log.message.emit("PLC 연결이 안전하게 해제되었습니다.", "INFO")

    def connect_with_retry(self, ui_callback: Optional[Callable[[str, int], None]] = None) -> bool:
        """
        재시도 로직을 포함한 연결 시도(블록킹 + UI 업데이트)

        인자:
            ui_callback(함수) : UI 진행률/메세지 업데이트용 함수
        """
        # 연결 시도 중일때는 연결 확인 중지
        self._stop_heartbeat_worker()

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

                # Model에게 연결하라고 시킴
                self.connector.connect()

                # 성공 처리
                success_msg = "TwinCAT 연결 성공! 시스템을 시작합니다."
                if ui_callback:
                    ui_callback(success_msg, 100)

                # 통신 상태 성공 시그널 방송
                EVENT_BUS.system.info.emit("TwinCAT 연결 성공")
                EVENT_BUS.conn.status_changed.emit(True)
                EVENT_BUS.log.message.emit(success_msg, "INFO")

                # 연결 감시자 투입
                self._start_heartbeat_worker()

                # 4. [NEW] Run Mode 보장
                if self.connector.ensure_run_mode():
                    EVENT_BUS.log.message.emit("TwinCAT Run Mode 확인 완료.", "INFO")
                else:
                    EVENT_BUS.log.message.emit("TwinCAT Run Mode 전환 실패! PLC 로직이 동작하지 않을 수 있습니다.", "CRITICAL")
                    # 실패 시 어떻게 할지 결정 (여기선 Critical 로그만 남기고 일단 진행 or 실패 처리)
                    # 현재 요구사항은 "켜지게 하려면" 이므로 실패하면 큰 문제임. 하지만 접속 자체는 성공했으니... 
                    # 사용자 알림을 위해 팝업을 띄우는게 좋겠지만, 일단 CRITICAL 로그로 충분
                
                QApplication.processEvents()
                time.sleep(0.5)
                return True

            except Exception as e:
                EVENT_BUS.log.message.emit(f"TwinCAT 접속 시도({i}) 실패: {e}", "ERROR")

                if i < max_retries:
                    if ui_callback:
                        ui_callback(f"접속 실패. 잠시 후 재시도...", progress)

                    # 대기(UI Freezing 방지)
                    end_time = time.time() + 1.0
                    while time.time() < end_time:
                        QApplication.processEvents()
                else:
                    EVENT_BUS.log.message.emit("TwinCAT 연결 실패", "CRITICAL")
                    return False

        return False



    # ==========================================================
    # Worker
    # ==========================================================
    def _create_worker(self, current_thread: QThread | None, command: str, data: Any = None, log_msg: str = "", force_interrupt: bool = False, cleanup_attrs: list[str] | None = None) -> tuple[QThread, PLCWorker] | None:
        """
        워커 스레드 생성 및 실행 공통 로직 (Factory Method)
        
        Args:
            current_thread: 현재 돌고 있는 스레드 (중복 실행 체크용)
            command: 실행할 명령
            data: 데이터
            log_msg: 시작 전 공지할 로그 메시지
            force_interrupt: True면 진행 중인 스레드를 무조건 중단하고 대기 (긴급)
            cleanup_attrs: 종료 시 None으로 초기화할 멤버 변수 이름 리스트 (예: ['_thread', '_worker'])
            
        Returns:
            (new_thread, new_worker) 튜플. 실행되지 않았다면 None.
        """

        # 1. 실행 중인 스레드 점검 및 처리
        if current_thread and current_thread.isRunning():
            if force_interrupt:
                # 긴급 작업은 기존 작업을 덮어쓰고 즉시 실행 (방어코드)
                current_thread.requestInterruption()
                current_thread.wait(100)
            else:
                # 일반 작업은 STOP 명령일 때만 기존 작업 중단
                if command == 'STOP':
                    current_thread.requestInterruption()
                else:
                    EVENT_BUS.log.message.emit("이전 작업이 아직 진행중입니다", "WARNING")
                    return None

        # 2. 로그
        if log_msg:
            EVENT_BUS.log.message.emit(log_msg, "INFO")

        # 사무실 계약
        thread = QThread()

        # 비서(Worker) 채용
        worker = PLCWorker(self.connector, self.commander, command, data)

        # 비서를 새 사무실로 전근 발령 - moveToThread() : 스레드 소속 변경
        worker.moveToThread(thread)


        # 비서의 전화보고(emit)를 받고 어떻게 처리(Slot)할지 미리 정해놓기(connect)
        worker.result.connect(self._handle_worker_result)
        
        # _cleanup이 파라미터를 받으므로 lambda나 partial로 인자 구워삶기(Binding)
        # 스레드와 워커가 종료될 때 이 특정 객체들을 정리하도록 지정함
        worker.finished.connect(lambda: self._cleanup(thread, worker, cleanup_attrs))
        
        # --- 사무실(Thread)에서 벌어질 이벤트 예약(connect) ---
        # 사무실 문 열리면 비서에게 “일 시작해라” 지시
        thread.started.connect(worker.run)
        # 사무실이 문 닫히면 → 사무실 정리하고 폐기하도록 예약
        thread.finished.connect(thread.deleteLater)
        
        # 사무실 오픈(스레드 시작)
        # 사무실 문을 열고 내부 이벤트 루프를 가동하는 것
        thread.start()
        
        return thread, worker

    def _cleanup(self, thread: QThread | None, worker: QObject | None, cleanup_attrs: list[str] | None = None):
        """
        실행 중인 스레드(사무실)와 워커(비서)를
        우아하게 종료하고 메모리 누수 없이 안전하게 폐기하는 함수
        """
        if thread and thread.isRunning():
            thread.quit()     # Thread의 이벤트 루프 종료 요청 - 남아 있는 이벤트 처리 후 종료
            thread.wait(2000) # 사무실이 안전하게 문 닫을 때까지 2초동안 기다림

        # 비서(Worker) 정리
        #   Qt의 메모리 관리 시스템에 맡겨서 안전하게 폐기
        #   파이썬 레퍼런스 해제는 아래 멤버변수 초기화에서 처리
        #   이미 삭제된 객체라면 안전하게 무시하도록 try-except 로 처리
        if worker:
            try:
                worker.deleteLater()    # Qt에게 삭제 요청
            except RuntimeError:
                pass

        # 사무실(Thread) 정리
        #   deleteLater는 '나중에' 지우라는 예약어이므로 즉시 None이 되지 않음.
        #   하지만 더 이상 이 변수를 쓰면 안 되므로, 파이썬 쪽 레퍼런스를 끊어야 함.
        #   이미 삭제된 객체라면 안전하게 무시하도록 try-except 로 처리
        if thread:
            try:
                thread.deleteLater()  # Qt에게 삭제 요청
            except RuntimeError:
                pass
            
        # 멤버 변수 초기화 (동적 처리)
        # cleanup_attrs에 지정된 멤버 변수들이 현재 정리 중인 객체와 같다면 None으로 초기화
        if cleanup_attrs:
            for attr_name in cleanup_attrs:
                if hasattr(self, attr_name):
                    current_obj = getattr(self, attr_name)
                    # 정리 대상인 thread나 worker와 동일한 객체를 가리키고 있을 때만 None 처리
                    # (이미 다른 작업이 시작되어 변수가 바뀌었을 수 있으므로 안전장치)
                    if current_obj == thread or current_obj == worker:
                        setattr(self, attr_name, None)

    def _start_worker(self, command: str, data: Any = None, log_msg: str = ""):
        """일반 작업 시작 (Wrapper)"""
        # 결과가 있을 때만 멤버 변수 업데이트
        if result := self._create_worker(self._thread, command, data, log_msg, force_interrupt=False, cleanup_attrs=['_thread', '_worker']):
            self._thread, self._worker = result

    def _start_emergency_worker(self, command: str, data: Any = None, log_msg: str = ""):
        """긴급 작업 시작 (Wrapper)"""
        # 결과가 있을 때만 멤버 변수 업데이트
        if result := self._create_worker(self._emergency_thread, command, data, log_msg, force_interrupt=True, cleanup_attrs=['_emergency_thread', '_emergency_worker']):
            self._emergency_thread, self._emergency_worker = result


    # ==========================================================
    # [비동기] 로봇 제어 명령 (Worker 사용)
    # ==========================================================
    def start_process(self):
        self._start_worker('START', log_msg="프로세스 시작 요청...")

    def stop_process(self):
        # 진행 중인 워커가 있다면 중단 요청
        if self._thread and self._thread.isRunning():
            self._thread.requestInterruption()
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 진행 중인 작업에 중단 요청을 보냈습니다.", "INFO")

            # 앱 충돌 방지 방어코드
            # 실행 중인 스레드 변수(_thread)를 덮어쓰면 앱이 죽는다(Crash)
            # 따라서 기존 작업자가 마무리하도록 신호만 보내고 새로운 작업자는 생성하지 않는다
            # 리턴이 없으면 아래의 _start_worker('STOP')가 실행되어 정리 중이던 스레드가 새로운 스레드에 의해서 쫓겨난다(참조가 사라짐) -> 앱 사망
            return

        # 만약 실행 중인 게 없다면, 그냥 정지 신호만 한 번 보내줌 (안전장치)
        self._start_worker('STOP', log_msg="프로세스 중지 요청...")

    def move_robot_by_pose(self, fanuc_pose_obj:FANUCPose):
        """
        좌표로 이동

            뷰,뷰모델,서비스:   앱 도메인 레이어
            워커:               백그라운드 작업자
            모델, 유틸리티 등:  하드웨어/인프라 레이어

            즉, 서비스 | 워커 이렇게 나뉘어진다
            그렇기 때문에 서비스 레이어인 여기서
                앱 도메인 모델(FANUCPose 객체) → 파이썬 자료형(딕셔너리, 리스트 등) 변환
        """

        # 딕셔너리로 변경
        fanuc_pose_data = fanuc_pose_obj.to_dict_preserving_key_names()

        # 리스트로 감싸서 sequence 형태로 만듦 (TwinCATCommander가 list[dict]를 기대함)
        sequence_data = [fanuc_pose_data]

        # Worker 호출
        self._start_worker('MOVE', data=sequence_data, log_msg=f"단일 명령 이동: {fanuc_pose_obj}")

    def process_sequence_data(self, csv_data: List[Dict[str, Any]]):
        """
        시퀀스 데이터를 받아 로봇 작업을 시작함
        Args:
            sequence_data (list): 실행할 시퀀스 리스트 (List[Dict])
        """
        # Worker 호출
        self._start_worker('MOVE', data=csv_data, log_msg=f"csv 시퀀스 명령: {len(csv_data)}건")

    def set_robot_speed(self, feed_rate: float):
        self._start_worker('SET_SPEED', data=feed_rate, log_msg=f"로봇 속도 설정 변경 요청: {feed_rate} mm/sec")


    # ==========================================================
    # [슬롯] Worker 시그널에 대한 처리
    # ==========================================================
    @pyqtSlot(bool, str) # type: ignore
    def _handle_worker_result(self, success: bool, msg: str):
        """워커 실행 결과 처리"""
        if not success:
            # 사용자에 의한 중단인 경우 팝업 띄우지 않음 및 로그 레벨 조정
            if "중단되었습니다" in msg or "User Stopped" in msg:
                EVENT_BUS.log.message.emit(msg, "INFO")
                # 팝업 알림 생략
                return
            
            # 그 외 진짜 에러 발생 시 사용자에게 팝업으로 알림 (제목, 내용)
            EVENT_BUS.system.operation_error_alert.emit("작업 실행 실패", msg)

        level = "INFO" if success else "ERROR"
        EVENT_BUS.log.message.emit(msg, level)

    # ==========================================================
    # [비동기] 서보 모터 제어 (Worker 사용)
    # ==========================================================
    def move_servo_by_manual(self, data: Dict[str, Any]):
        """
        서보 수동 조작
        
        Args:
            data (dict): {'axis': 1, 'velocity': 10.0, 'target': ...} 등의 제어 정보
        """
        EVENT_BUS.log.message.emit(f"서보 구동 요청: {data}", "DEBUG")
        # Commander는 list[dict] 형태를 기대하므로 리스트로 포장
        sequence_data = [data]
        # 이동하는건 'MOVE' 명령으로 통일 (Commander가 알아서 Executor를 찾음)
        self._start_worker('MOVE', data=sequence_data, log_msg=f"서보 구동 요청: {data}")

    def stop_servo_all(self):
        """서보 모터 비상 정지"""
        
        # 만약 이미 무언가(예: 로봇 이동) 실행 중이라면 강제 중단 요청
        if self._thread and self._thread.isRunning():
            self._thread.requestInterruption()
            EVENT_BUS.log.message.emit("진행 중인 작업을 중단하고 서보 정지를 시도합니다.", "WARNING")

        # 정지 명령 Worker 실행 (긴급 스레드 사용)
        # 만약 여기서 기존 스레드가 끝나길 기다리면(Wait), 원점 복귀 루프가 끝나지 않아서(Move가 안 멈춤) 데드락에 걸림.
        # 따라서 병렬로 "즉시" 정지 신호를 쏴줘야 함.
        self._start_emergency_worker('SERVO_STOP', log_msg="서보 전체 정지 요청")

    def home_servo_all(self):
        """서보 원점 복귀"""
        # 원점 복귀는 시간이 걸리는 작업이므로 Worker로 실행
        self._start_worker('SERVO_HOME', log_msg="서보 원점 복귀 요청 (Axis 1,2,3)")

    def reset_servo_all(self):
        """서보 에러 리셋"""
        # 에러 리셋은 비교적 빠르지만, PLC 통신이 포함되므로 Worker로 실행
        self._start_worker('SERVO_RESET', log_msg="서보 에러 리셋 요청")






    # ==========================================================
    # 상태 확인
    # ==========================================================
    @property
    def is_running(self) -> bool:
        """로봇이나 서보 모터가 현재 작업 중인지 확인"""

        # 연결이 끊겼는가? (연결 없으면 상태 확인 불가)
        if not self.connector.is_connected:
            return False

        # 스레드(Python)가 일하고 있는가?
        if self._thread is not None and self._thread.isRunning():
            return True

        # Gadgets(로봇과 서보모터)가 움직이고 있는가?
        return self.commander.are_gagets_busy()



    # ==========================================================
    # 기기의 현재 위치 모니터링
    # ==========================================================
    def _on_connectino_changed(self, is_connected: bool):
        """연결되면 모니터링 시작, 끊기면 중지"""
        if is_connected:
            self._start_monitoring()
        else:
            self._stop_monitoring()

    def _start_monitoring(self):
        """모니터링 스레드 시작"""
        if self._pose_monitor_thread is not None: return     # 이미 실행중

        # 1. 스레드 및 워커 생성 (지역 변수를 사용하여 Pylance None 체크 통과)
        thread = QThread()
        worker = PoseMonitorWorker(self.commander)

        self._pose_monitor_thread = thread
        self._pose_monitor_worker = worker
        
        # 2. 워커를 스레드로 이동
        worker.moveToThread(thread)
        
        # 3. 시그널 연결 (스레드 생명주기 관리)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # 스레드 정리 시 변수 초기화 연결
        thread.finished.connect(self._clear_monitor_refs)

        thread.start()
        EVENT_BUS.log.message.emit("모니터링 스레드가 시작되었습니다.", "INFO")

    def _stop_monitoring(self):
        """모니터링 중지"""
        if self._pose_monitor_worker:
            self._pose_monitor_worker.stop()     # 루프 탈출 플래그 설정

    def _clear_monitor_refs(self):
        """스레드 종료 후 레퍼런스 초기화"""
        self._pose_monitor_thread = None
        self._pose_monitor_worker = None


    # ==========================================================
    # 연결 상태(Heartbeat) 모니터링 (Worker 관리)
    # ==========================================================
    def _start_heartbeat_worker(self):
        """연결 감시 스레드 시작"""
        if self._heartbeat_thread is not None: return

        thread = QThread()
        worker = HeartbeatWorker(self.connector, interval=2.0)

        self._heartbeat_thread = thread
        self._heartbeat_worker = worker
        
        worker.moveToThread(thread)

        # 시그널 연결
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_conn_refs)

        # [중요] 연결 끊김 보고 받으면 처리할 메서드 연결
        worker.connection_lost.connect(self._handle_connection_lost)

        thread.start()

    def _stop_heartbeat_worker(self):
        """연결 감시 중지"""
        if self._heartbeat_worker:
            self._heartbeat_worker.stop()
            # 스레드가 종료될 때까지 잠시 대기 (안전한 종료)
            if self._heartbeat_thread:
                self._heartbeat_thread.wait(100)

    def _clear_conn_refs(self):
        """참조 초기화"""
        self._heartbeat_thread = None
        self._heartbeat_worker = None

    @pyqtSlot()
    def _handle_connection_lost(self):
        """
        [비상] 워커가 연결 끊김을 감지했을 때 호출됨
        기존 _check_heartbeat 로직을 여기서 처리
        """
        # 스레드 정리
        self._stop_heartbeat_worker()

        # UI 및 시스템 알림 방송
        EVENT_BUS.conn.status_changed.emit(False)
        EVENT_BUS.log.message.emit("⚠️ TwinCAT 연결 끊김 감지! (Heartbeat Lost)", "ERROR")
        EVENT_BUS.system.error.emit("TwinCAT_DISCONNECTED")
