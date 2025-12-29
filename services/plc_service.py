# services/plc_service.py
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, QTimer, pyqtSlot, QThread, Qt, QMetaObject

from typing import Any, Dict, List
from core.event_bus import EVENT_BUS
from workers.plc_worker import PLCWorker
from models.fanuc_pose_model import FANUCPose
from models.servo_pose_model import ServoPose
from communication.twincat_connector import TwinCATConnector
from communication.twincat_commander import TwinCATCommander
from communication.fanuc_adapter import FanucAdapter
from communication.servo_adapter import ServoAdapter
from models.servo_pose_key import ServoAxis




class PLCService(QObject):
    """
    하드웨어 관리소
        애플리케이션의 하드웨어 제어 계층에서 'Composition Root' 역할 수행
    """
    def __init__(self):
        super().__init__()
        self._log_prefix = f"[{self.__class__.__name__}]"
        
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


        # --- TwinCAT 연결 상태 정기적으로 확인 (Heartbeat) --- #
        self._heartbeat_timer = QTimer()
        self._heartbeat_timer.setInterval(2000) # 2초마다
        self._heartbeat_timer.timeout.connect(self._check_heartbeat)


        # --- 현재위치 모니터링 타이머(0.1초마다) --- #
        self._monitor_timer = QTimer()
        self._monitor_timer.setInterval(100)  # 0.1초마다 실행 (10Hz)
        self._monitor_timer.timeout.connect(self._on_monitor_tick)


        # --- 앱 종료 시 연결 끊기 --- #
        # AppEngine이 종료 신호를 보내면 -> disconnect_plc 메서드가 자동 실행됨
        EVENT_BUS.system.shutting_down.connect(self.disconnect_plc)



    # ==========================================================
    # 연결 관련 메서드
    # ==========================================================

    @pyqtSlot()
    def disconnect_plc(self):
        """연결 해제 (앱 종료 시 or 수동 끊기)"""

        # 타이머 먼저 정지 (죽은 연결을 체크하지 않도록)
        self._heartbeat_timer.stop()
        self._monitor_timer.stop()
        
        if self.connector.is_connected:
            self.connector.disconnect()
            EVENT_BUS.conn.status_changed.emit(False)
            EVENT_BUS.log.message.emit("PLC 연결이 안전하게 해제되었습니다.", "INFO")


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

                # Heartbeat 타이머 시작
                self._heartbeat_timer.start()

                # 현재위치 모니터링 타이머 시작
                self._monitor_timer.start()
                
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


    def _check_heartbeat(self):
        """2초마다 실행되어 연결 상태 확인"""

        # Model의 check_connection 호출
        is_alive = self.connector.check_connection()
        
        if not is_alive:
            self._heartbeat_timer.stop()

            # --- 비상 상황 알림 --- #
            # 통신 연결 상태 변경 시그널 emit
            EVENT_BUS.conn.status_changed.emit(False)
            EVENT_BUS.log.message.emit("⚠️ TwinCAT 연결 끊김 감지!", "ERROR")

            # 시스템 에러 발생 시그널 emit
            EVENT_BUS.system.error.emit("TwinCAT_DISCONNECTED")



    # ==========================================================
    # [비동기] 로봇 제어 명령 (Worker 사용)
    # ==========================================================
    def _start_worker(self, command: str, data=None, log_msg: str = ""):
        """비동기 워커 스레드 생성 및 실행 (공통 로직)"""

        if self._thread and self._thread.isRunning():
            if command == 'STOP':
                self._thread.requestInterruption()  # 강제 중단 요청
            else:
                EVENT_BUS.log.message.emit("이전 작업이 아직 진행중입니다", "WARNING")
                return # 이전 작업이 있다면 중복 실행 방지

        if log_msg:
            EVENT_BUS.log.message.emit(log_msg, "INFO")

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


    def process_sequence_data(self, csv_data: list):
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
    # 상태 확인
    # ==========================================================
    @property
    def is_running(self) -> bool:
        """로봇이나 턴테이블이 현재 작업 중인지 확인"""

        # 연결이 끊겼는가? (연결 없으면 상태 확인 불가)
        if not self.connector.is_connected:
            return False

        # 스레드(Python)가 일하고 있는가?
        if self._thread is not None and self._thread.isRunning():
            return True

        # Gadgets(로봇&턴테이블)이 움직이고 있는가?
        return self.commander.are_gagets_busy()



    # ==========================================================
    # [슬롯] Worker 시그널에 대한 처리
    # ==========================================================
    @pyqtSlot(bool, str)
    def _handle_worker_result(self, success: bool, msg: str):
        """워커 실행 결과 처리"""
        level = "INFO" if success else "ERROR"
        EVENT_BUS.log.message.emit(msg, level)

    @pyqtSlot()
    def _cleanup(self):
        """
        실행 중인 스레드(사무실)와 워커(비서)를
        우아하게 종료하고 메모리 누수 없이 안전하게 폐기하는 함수
        """
        if self._thread and self._thread.isRunning():
            self._thread.quit()     # Thread의 이벤트 루프 종료 요청 - 남아 있는 이벤트 처리 후 종료
            self._thread.wait(2000) # 사무실이 안전하게 문 닫을 때까지 2초동안 기다림

        # 비서(Worker) 정리
        if self._worker:
            self._worker.deleteLater()  # 비서 정리 → Qt의 메모리 관리 시스템에 맡겨서 안전하게 폐기
            self._worker = None         # Python 레벨에서도 비서 레퍼런스 해제(메모리 누수 방지)

        # 사무실(Thread) 정리
        if self._thread:
            # deleteLater는 '나중에' 지우라는 예약어이므로 즉시 None이 되지 않음.
            # 하지만 더 이상 이 변수를 쓰면 안 되므로, 파이썬 쪽 레퍼런스를 끊어야 함.
            self._thread.deleteLater()  # Qt에게 삭제 요청
            self._thread = None         # [핵심] 파이썬 변수 초기화

    # ==========================================================
    # 실시간 데이터 수집 루프
    # ==========================================================
    def _on_monitor_tick(self):
        """
        0.1초마다 실행되어 로봇/턴테이블의 현재 상태를 읽고 UI에 방송
        """
        if not self.connector.is_connected: return

        try:
            # --- 1. 위치 방송 (FANUC World 좌표)--- #
            # FANUC World 현재 위치 읽기 & 방송
            world_pose = self.commander.robot.read_current_world_pose()
            EVENT_BUS.control.robot_current_pose.emit(world_pose)

            # FANUC 이동해야 될 목표 위치 확인 & 방송 <- 개발용
            # target_pose = self.commander.robot.read_target_world_pose()
            # EVENT_BUS.control.tool_current_pose.emit(target_pose)

            # --- 2. 서보모터 상태 방송 --- #
            # 3개 축의 데이터를 담을 딕셔너리 생성
            servo_states = {}
            for axis in ServoAxis:
                # 어댑터에서 데이터(딕셔너리) 읽기
                raw_data = self.commander.servo.read_current_servo_motion(axis)

                # ServoPose 모델로 Mapping
                servo_states[axis] = ServoPose(
                    angle=raw_data['position'],
                    velocity=raw_data['velocity']
                )
            
            # 방송 -> Dict[int, ServoPose] 형태
            EVENT_BUS.control.servo_current_motion.emit(servo_states)

            # --- 3. 바쁨 상태 방송 --- #
            is_busy = self.is_running
            EVENT_BUS.data.servo_busy_status.emit({'is_busy': is_busy})

        except Exception as e:
            # 모니터링 중 에러는 로그를 남기지 않음 (로그 폭주 방지)
            pass



    # ==========================================================
    # [비동기] 서보 모터 제어 (Worker 사용)
    # ==========================================================
    
    def move_servo_by_manual(self, data: dict):
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

        # 정지 명령 Worker 실행
        self._start_worker('SERVO_STOP', log_msg="서보 전체 정지 요청")


    def home_servo_all(self):
        """서보 원점 복귀"""
        # 원점 복귀는 시간이 걸리는 작업이므로 Worker로 실행
        self._start_worker('SERVO_HOME', log_msg="서보 원점 복귀 요청 (Axis 1,2,3)")


    def reset_servo_all(self):
        """서보 에러 리셋"""
        # 에러 리셋은 비교적 빠르지만, PLC 통신이 포함되므로 Worker로 실행
        self._start_worker('SERVO_RESET', log_msg="서보 에러 리셋 요청")
