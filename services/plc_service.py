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



class WorkerID:
    """워커 식별자 상수"""
    SEQUENCE = "robot_servo_sequence"
    FANUC_ONLY = "fanuc_only"
    SERVO_ONLY = "servo_only"
    SERVO_HOME = "home_servo_all"
    SERVO_RESET = "reset_servo_all"
    SET_SPEED = "set_speed"
    EMERGENCY = "emergency_stop"
    ROBOT_STOP = "robot_stop"
    SERVO_STOP = "servo_stop"


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
        # 여러개의 워커를 저장해 놓을 딕셔너리
        # 새로운 사무실(QThread) '공간 확보'
        # 비서(Worker) 직군 '정원 확보'
        # Key: WorkerID (str), Value: (QThread, PLCWorker)
        self._active_workers: Dict[str, tuple[QThread, PLCWorker]] = {}

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

        # 1. 모든 워커 및 모니터링 스레드 종료 및 정리
        # (disconnect 시에는 Emergency 워커도 포함해서 모두 끔)
        self._stop_all_working_threads_and_workers_on_background()
        self._stop_all_monitoring_threads()

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
    # Thread & Worker
    # ==========================================================
    def _create_worker(self, current_thread: QThread | None, command: str, data: Any = None, log_msg: str = "", force_interrupt: bool = False, cleanup_attrs: list[str] | None = None, worker_id: str | None = None) -> tuple[QThread, PLCWorker] | None:
        """
        워커 스레드 생성 및 실행 공통 로직 (Factory Method)
        
        Args:
            current_thread:     현재 실행 중인 스레드 (중복 실행 체크용) -> worker_id가 있으면 무시됨
            command:            실행할 명령
            data:               데이터
            log_msg:            시작 전 공지할 로그 메시지
            force_interrupt:    True면 진행 중인 스레드를 무조건 중단하고 대기 (긴급)
            cleanup_attrs:      종료 시 None으로 초기화할 멤버 변수 이름 리스트
            worker_id:          워커 식별자 ID -> 딕셔너리 관리용
            
        Returns:
            생성된 스레드와 워커를 담은 튜플. 실행되지 않았다면 None 반환
        """

        # 1. 실행 중인 스레드 점검 및 처리
        target_thread = current_thread
        
        # worker_id가 제공되었다면 해당 ID로 이미 실행 중인 스레드가 있는지 딕셔너리에서 찾아본다
        #   동일한 ID의 작업이 중복 실행되는 것을 방지하거나 비상 정지 시 해당 스레드를 찾아 멈추기 위함
        if worker_id:
            if worker_id in self._active_workers:
                target_thread, _ = self._active_workers[worker_id]

        # 중복 실행 체크
        if target_thread and target_thread.isRunning():
            # 긴급 작업
            if force_interrupt:
                # 기존 작업이 있어도 덮어쓰고 즉시 실행 (방어코드)
                target_thread.requestInterruption()
                target_thread.wait(100)
            else:
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 이전 작업이 아직 진행중입니다", "WARNING")
                return None

        # 2. 로그
        if log_msg:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} {log_msg}", "INFO")

        # 사무실 계약
        thread = QThread()

        # 비서(Worker) 채용
        worker = PLCWorker(self.connector, self.commander, command, data)

        # 비서를 새 사무실로 전근 발령 - moveToThread() : 스레드 소속 변경
        worker.moveToThread(thread)

        # --- 작업 처리 예약 --- #
        # 비서의 보고(emit)를 받으면 어떻게 처리(Slot)할지 미리 정해놓기(connect)
        worker.result.connect(self._handle_worker_result)
        
        # --- 정리 예약 --- #
        # 작업이 정상적으로 끝나면 워커의 로컬시그널 finished가 실행된다.
        # 1. 워커 객체 자동 삭제 예약
        worker.finished.connect(worker.deleteLater)
        # 2. _cleanup 호출하여 딕셔너리 정리 및 스레드 종료
        worker.finished.connect(lambda: self._cleanup(thread, worker, cleanup_attrs, worker_id))
        
        # --- 사무실(Thread)에서 벌어질 이벤트 예약(connect) --- #
        # 사무실 문 열리면 비서에게 “일 시작해라” 지시
        thread.started.connect(worker.run)
        # 사무실이 문 닫히면 → 사무실 정리하고 폐기하도록 예약
        thread.finished.connect(thread.deleteLater)
        
        # 사무실 오픈(스레드 시작)
        # 사무실 문을 열고 내부 이벤트 루프를 가동하는 것
        thread.start()
        
        return thread, worker

    def _cleanup(self, thread: QThread | None = None, worker: QObject | None = None, cleanup_attrs: list[str] | None = None, worker_id: str | None = None):
        """
        실행 중인 스레드(사무실)와 워커(비서)를
        우아하게 종료하고 메모리 누수 없이 안전하게 폐기하는 함수
        """
                
        # 1. worker_id가 있으면 딕셔너리에서 객체를 찾아옴 (없으면 None)
        active_thread = None
        active_worker = None
        
        if worker_id and worker_id in self._active_workers:
            active_thread, active_worker = self._active_workers[worker_id]
            
            # 파라미터로 thread/worker를 안 넘겨줬으면 딕셔너리에 있는걸 정리 대상으로 삼음
            if thread is None: thread = active_thread
            if worker is None: worker = active_worker
            
            # [중요] 만약 파라미터로 받은 thread와 딕셔너리에 있는 thread가 다르면?
            # -> 이미 다른 새 작업이 그 ID로 시작됐다는 뜻이므로, 딕셔너리(self._active_workers)를 건드리면 안 됨!
            if thread != active_thread:
                worker_id = None 
    
        # 2. 정리 작업 수행
        if thread and thread.isRunning():
            thread.quit()     # Thread의 이벤트 루프 종료 요청 - 남아 있는 이벤트 처리 후 종료
            # thread.wait(2000) # [제거] UI 스레드에서 wait을 호출하면 화면이 멈춤 (Freezing)
            
        # 해당 ID의 워커를 딕셔너리에서 제거
        if worker_id:
            self._active_workers.pop(worker_id, None)
            
        # [Legacy] 멤버 변수 초기화 (동적 처리 - 비상 정지용)
        # cleanup_attrs에 지정된 멤버 변수들이 현재 정리 중인 객체와 같다면 None으로 초기화
        if cleanup_attrs:
            for attr_name in cleanup_attrs:
                if hasattr(self, attr_name):
                    current_obj = getattr(self, attr_name)
                    # 정리 대상인 thread나 worker와 동일한 객체를 가리키고 있을 때만 None 처리
                    # (이미 다른 작업이 시작되어 변수가 바뀌었을 수 있으므로 안전장치)
                    if current_obj == thread or current_obj == worker:
                        setattr(self, attr_name, None)

    def _start_worker(self, command: str, worker_id: str, data: Any = None, log_msg: str = ""):
        """일반 작업 시작 (Wrapper) - Dictionary Mode 필수"""
        if result := self._create_worker(None, command, data, log_msg, force_interrupt=False, worker_id=worker_id):
            # 생성된 스레드와 워커를 딕셔너리에 저장
            self._active_workers[worker_id] = result

    def _stop_worker(self, command: str, worker_id: str, data: Any = None, log_msg: str = ""):
        """정지 작업 시작 (Wrapper)"""
        # 일반적인 정지 후 곧바로 비상정지를 눌러도 마지막 비상정지 명령이 실행될 수 있게(= 실행중 스레드를 무시) force_interrupt=True로 설정
        if result := self._create_worker(None, command, data, log_msg, force_interrupt=True, worker_id=worker_id):
            self._active_workers[worker_id] = result

    def _stop_all_working_threads_and_workers_on_background(self, exclude_emergency: bool = False):
        """실행 중인 모든 백그라운드 워커 중지 및 정리"""
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 모든 백그라운드 작업 정지 및 정리 시작...", "INFO")

        # 딕셔너리에 있는 워커들 정리
        for w_id in list(self._active_workers.keys()):
            if exclude_emergency and w_id == WorkerID.EMERGENCY:
                continue
            
            thread, worker = self._active_workers[w_id]
            if thread.isRunning():
                thread.requestInterruption()
            
            # _cleanup 호출하여 스레드 종료 대기 및 메모리 정리
            self._cleanup(thread, worker, worker_id=w_id)

    def _stop_all_monitoring_threads(self):
        """실행 중인 모든 모니터링/감시 스레드 중지 및 정리"""
        # 모니터링/감시 스레드 중지 및 정리
        self._stop_monitoring()
        self._stop_heartbeat_worker()
        
        self._cleanup(self._pose_monitor_thread, self._pose_monitor_worker, ['_pose_monitor_thread', '_pose_monitor_worker'])
        self._cleanup(self._heartbeat_thread, self._heartbeat_worker, ['_heartbeat_thread', '_heartbeat_worker'])



    # ==========================================================
    # [슬롯] 시그널 핸들링
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
    # 상태 쿼리
    #    현재 시스템이 특정 작업을 할 수 있는지, 상태가 어떤지 확인
    # ==========================================================
    def is_runnable(self) -> bool:
        """
        새로운 작업을 시작할 수 있는지 확인
        - 이전의 시퀀스 작업이 살아있으면 False (정지 중이거나 작업 중)
        """
        if WorkerID.SEQUENCE in self._active_workers:
            thread, _ = self._active_workers[WorkerID.SEQUENCE]
            if thread.isRunning():
                return False
        return True

    def is_connected(self):
        """"""
        # TODO: PLC 연결 상태 확인
        return True


    # ==========================================================
    # [비동기] 로봇 제어 명령 (Worker 사용)
    # ==========================================================
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
        self._start_worker('MOVE', worker_id=WorkerID.FANUC_ONLY, data=sequence_data, log_msg=f"FANUC 단독 이동 위한 워커 호출: {fanuc_pose_obj}")

    def set_robot_speed(self, feed_rate: float):
        self._start_worker('SET_SPEED', worker_id=WorkerID.SET_SPEED, data=feed_rate, log_msg=f"로봇 속도 설정 변경 요청: {feed_rate} mm/sec")


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
        self._start_worker('MOVE', worker_id=WorkerID.SERVO_ONLY, data=sequence_data, log_msg=f"서보 단독 구동 위한 워커 호출: {data}")

    def home_servo_all(self):
        """서보 원점 복귀"""
        # 원점 복귀는 시간이 걸리는 작업이므로 Worker로 실행
        self._start_worker('SERVO_HOME', worker_id=WorkerID.SERVO_HOME, log_msg="서보 원점 복귀 요청 (Axis 1,2,3)")

    def reset_servo_all(self):
        """서보 에러 리셋"""
        # 에러 리셋은 비교적 빠르지만, PLC 통신이 포함되므로 Worker로 실행
        self._start_worker('SERVO_RESET', worker_id=WorkerID.SERVO_RESET, log_msg="서보 에러 리셋 요청")

    def stop_servo_all(self):
        """서보 모터 정지"""
        
        # 관련 워커(시퀀스, 서보 이동/원점/리셋) 중단 요청
        targets = [WorkerID.SEQUENCE, WorkerID.SERVO_ONLY, WorkerID.SERVO_HOME, WorkerID.SERVO_RESET]
        
        for w_id in targets:
            if w_id in self._active_workers:
                thread, _ = self._active_workers[w_id]
                if thread.isRunning():
                    # thread.requestInterruption()을 호출하면 ->
                    # 워커 내부 루프(while not isInterruptionRequested())가 깨지고 ->
                    # process_... 메서드가 리턴(종료)되면 ->
                    # PLCWorker.run() 메서드가 끝나면서 finished 시그널 방출 ->
                    # _create_worker를 통해 스레드를 만들 때 연결해둔 _cleanup이 자동으로 호출됨
                    thread.requestInterruption()

        # 정지 명령 전송
        self._stop_worker('SERVO_STOP', worker_id=WorkerID.SERVO_STOP, log_msg="모든 서보모터 정지")
        
        EVENT_BUS.log.message.emit("진행 중인 서보 작업을 중단합니다.", "WARNING")


    # ==========================================================
    # [비동기] 로봇 & 서보 제어
    # ==========================================================
    def process_sequence_data(self, csv_data: List[Dict[str, Any]]):
        """
        시퀀스 데이터를 받아 로봇 작업을 시작함
        Args:
            sequence_data (list): 실행할 시퀀스 리스트 (List[Dict])
        """
        # Worker 호출
        self._start_worker('MOVE', worker_id=WorkerID.SEQUENCE, data=csv_data, log_msg=f"csv 시퀀스 처리 위한 워커 호출: {len(csv_data)}건")

    def trigger_emergency_stop(self):
        """[비상 정지] 모든 장치 및 작업 강제 중단 요청"""
        
        EVENT_BUS.log.message.emit("🚨 비상 정지 발동! 모든 작업을 강제 중단합니다.", "CRITICAL")
        
        # 1. [최우선] 긴급 워커로 물리적 장비 비상 정지 명령 전송 (로봇 + 서보)
        #    S/W적으로 스레드 정리하는 시간조차 아까우므로 일단 정지 신호부터 보냄
        self._stop_worker('EMERGENCY_STOP', worker_id=WorkerID.EMERGENCY)

        # 2. 모든 일반 워커 중지 (비상 정지 워커는 제외)
        #    이미 실행된 비상 정지 워커를 끄지 않도록 exclude_emergency=True
        self._stop_all_working_threads_and_workers_on_background(exclude_emergency=True)

    def stop_processing_job(self):
        """
        [작업 중단] 진행 중인 프로세스 중단 및 장비 정지
        1. 논리적 중단: 작업 스레드에게 Interruption 요청
        2. 물리적 정지: 로봇/서보에게 정지 신호 전송 (별도 워커 사용)
        """
        # 1. 시퀀스 워커가 진행 중이라면
        if WorkerID.SEQUENCE in self._active_workers:
            # 현재 돌고있는 스레드 중에서 `WorkerID.SEQUENCE` 이름으로 돌고 있는 스레드와 워커 객체만 뽑아오기
            thread, worker = self._active_workers[WorkerID.SEQUENCE]
            
            if thread.isRunning():
                # 여기서 requestInterruption()을 호출하면 -> 
                # 워커 내부 루프 종료 -> 
                # run() 리턴 ->
                # finished 시그널 방출 -> 
                # 스레드를 만들 때(_create_worker) 연결을 예약해둔 _cleanup 자동 호출 ->
                # 딕셔너리(self._active_workers)에서 해당 스레드/워커 제거 및 메모리 해제
                # 즉, 여기서 명시적으로 _cleanup을 부르지 않아도 알아서 정리됨. (오히려 부르면 충돌남)
                thread.requestInterruption()
                
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 진행 중인 작업 루프 중단 요청 및 정리 완료", "INFO")

        # 2. 물리적 장비 정지 명령 전송
        self._stop_worker('STOP_ROBOT_SERVO', worker_id=WorkerID.SEQUENCE, log_msg="서보와 로봇 정지 명령 전송")



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
