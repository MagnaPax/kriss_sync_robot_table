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
from communication.fanuc_adapter import FanucAdapter
from config.data_formats import *
from typing import Dict, List, Any, Optional
from core.event_bus import EVENT_BUS



class PLCWorker(QObject):

    # 로컬 시그널 정의
    finished = pyqtSignal()              # 작업 종료 알림
    result = pyqtSignal(bool, str)       # 결과 (성공여부, 메시지)


    def __init__(self, connector: TwinCATConnector, commander: TwinCATCommander, command: str, sequence_data: Optional[List[dict[str, Any]]]):
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
        self.sequence_data = sequence_data


    @pyqtSlot()
    def run(self):
        """스레드가 시작되면 호출되는 진입점"""

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

                    # 데이터 유효성 검사 (None 체크)
                    if self.sequence_data is None:
                        raise ValueError("MOVE 명령에 필요한 데이터가 없습니다.")

                    # Commander 호출 (데이터 형식에 맞는 Executor를 찾아 실행)
                    # find_executor는 (bool, str) 튜플을 반환합니다.
                    is_success, msg = self.commander.execute_sequence_with_executor(self.sequence_data)


                # --- 제어 명령 (Commander 사용) --- #
                # case 'START':
                #     is_success, msg = self.commander.start_sequence_plc_signals()
                # case 'STOP':
                #     is_success, msg = self.commander.end_sequence_plc_signals()
                # case _:
                #     msg = "알 수 없는 명령입니다."
                #     pass

        # -----------------------------------------------------------
        # 예외 처리 (로그는 Service가 남기므로 여기선 실패 사유만 전달)
        # -----------------------------------------------------------
        except InterruptedError:
            is_success = False
            msg = "작업이 사용자에 의해 중단됨"

        except Exception as e:
            is_success = False
            msg = f"작업중 오류 발생: {e}"


        # 결과 보고 및 종료
        self.result.emit(is_success, msg)
        self.finished.emit()


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
