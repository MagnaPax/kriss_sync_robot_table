# workers/plc_worker.py
"""
백그라운드 스레드에서 PLC 제어 로직을 수행하는 작업자

Worker는 '스레드 + 실행 관리자'
    데이터를 변환하거나 해석하거나 로봇 프로토콜을 몰라야 한다
    그래야 Worker는 교체 가능하고 각 브랜드의 로봇을 구분하지 않아도 된다

역할:
    모델 호출
    stop flag 체크
    결과 emit

특징:
    - UI 프리징(멈춤)을 방지하기 위해 별도 스레드에서 동작
    - 직접 로그를 남기지 않고, 결과(result) 시그널로 성공/실패 여부만 보고함
"""
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
from communication.twincat_connector import TwinCATConnector
from communication.twincat_commander import TwinCATCommander
from config.data_formats import *
from typing import Any
from core.event_bus import EVENT_BUS
from core.exceptions import AppError



class PLCWorker(QObject):

    # 로컬 시그널 정의
    finished = pyqtSignal()              # 작업 종료 알림
    result = pyqtSignal(bool, str)       # 결과 (성공여부, 메시지)


    def __init__(self, connector: TwinCATConnector, commander: TwinCATCommander, command: str, data: Any):
        """
        Args:
            connector: '연결' 관리를 위한 객체
            commander: 로봇 '제어' 명령을 위한 객체
            command: 실행할 명령 종류 ('CONNECT', 'MOVE', 'START' 등)
            data: 명령 실행에 필요한 데이터 (좌표 등)
        """
        super().__init__()

        # 로그 메세지의 말머리(로그 발생 위치 표시)
        self._log_prefix = f"[{self.__class__.__name__}]"

        self.connector = connector
        self.commander = commander
        self.command = command
        self.data = data


    @pyqtSlot()
    def run(self):
        """스레드가 시작되면 호출되는 진입점"""

        # QThread에서 브레이크포인트가 안 잡히는 문제 해결을 위해 디버거 강제 연결
        try:
            import debugpy
            debugpy.debug_this_thread()
        except (ImportError, Exception):
            # 디버거가 없거나 연결 불가 시 조용히 넘어감
            pass

        is_success = False
        msg = "알 수 없는 명령입니다."

        try:
            match self.command:

                # --- 연결 명령 (Connector 사용) --- #
                case 'CONNECT':
                    self.connector.connect()
                    is_success = True
                    msg = f"TwinCAT 연결 성공 ({self.connector.ams_net_id})"


                # --- 이동 명령 (Commander 사용) --- #
                case 'MOVE':
                    if self.data is None: raise ValueError("MOVE 명령에 필요한 데이터가 없습니다.")
                    is_success, msg = self.commander.execute_sequence_with_executor(self.data)  # 넘겨주는 데이터 형식에 맞는 Executor를 찾아서 실행

                case 'SET_SPEED':
                    EVENT_BUS.log.message.emit(f"{self._log_prefix} 이동속도:{self.data}\n데이터 타입: {type(self.data)}", "DEBUG")
                    result_msg = self.commander.apply_user_feed_rate_when_moving_robot(float(self.data))
                    if result_msg: self.result.emit(True, result_msg)


                # --- 제어 명령 (Commander 사용) --- #
                case 'START':
                    is_success, msg = self.commander.start_sequence_plc_signals()
                case 'STOP':
                    is_success, msg = self.commander.end_sequence_plc_signals()


                # --- 서보 전용 제어 명령 (Commander 사용) --- #
                case 'SERVO_STOP':
                    is_success, msg = self.commander.shutdown_servos_safely()   # 안전 정지 및 전원 차단
                case 'SERVO_HOME':
                    is_success, msg = self.commander.home_servos_safely()        # 안전 원점 복귀
                case 'SERVO_RESET':
                    is_success, msg = self.commander.reset_servos_safely()      # 서보모터 축의 에러 해제
                case _:
                    msg = "알 수 없는 명령입니다."

        # -----------------------------------------------------------
        # 예외 처리 (로그는 Service가 남기므로 여기선 실패 사유만 전달)
        # -----------------------------------------------------------
        except InterruptedError:
            is_success = False
            msg = "작업이 사용자에 의해 중단됨"

        # 커스텀 비즈니스 로직 예외 (ServoBusyError, ServoFaultError 등)
        except AppError as e:
            is_success = False
            msg = str(e)  # "작업중 오류 발생" 접두어 없이 원본 메시지 그대로 전달

        except Exception as e:
            is_success = False
            msg = f"작업중 오류 발생: {e}"

        # 결과 보고 및 종료
        # 결과 보고 및 종료
        try:
            self.result.emit(is_success, msg)
            self.finished.emit()
        except RuntimeError:
            pass


    def _is_interrupted(self) -> bool:
        """
        [중단 확인 콜백]
        TwinCATCommander가 긴 루프를 돌 때,
        사용자가 '정지' 버튼을 눌렀는지 주기적으로 확인하기 위해 호출
        """
        current_thread = QThread.currentThread()
        if current_thread:
            return current_thread.isInterruptionRequested()
        return False
