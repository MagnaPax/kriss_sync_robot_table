# workers/plc_worker.py
"""
백그라운드 스레드에서 PLC 제어 로직을 수행하는 작업자

특징:
    - UI 프리징(멈춤)을 방지하기 위해 별도 스레드에서 동작
    - 직접 로그를 남기지 않고, 결과(result) 시그널로 성공/실패 여부만 보고함
"""
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
from communication.twincat_connector import TwinCATConnector
from communication.fanuc_adapter import FanucAdapter
from config.data_formats import *
from typing import Dict, List, Any
from core.event_bus import EVENT_BUS



class PLCWorker(QObject):

    # 로컬 시그널 정의
    finished = pyqtSignal()              # 작업 종료 알림
    result = pyqtSignal(bool, str)       # 결과 (성공여부, 메시지)


    def __init__(self, connector: TwinCATConnector, commander: FanucAdapter, command: str, data=None):
        """
        Args:
            connector: '연결' 관리를 위한 객체
            commander: 로봇 '제어' 명령을 위한 객체
            command: 실행할 명령 종류 ('CONNECT', 'MOVE', 'START' 등)
            data: 명령 실행에 필요한 데이터 (좌표 등)
        """
        super().__init__()
        self.connector = connector
        self.commander = commander
        self.command = command
        self.data = data


    @pyqtSlot()
    def run(self):
        """스레드가 시작되면 호출되는 진입점"""

        success = False
        msg = "알 수 없는 명령입니다."

        try:
            match self.command:

                # --- 연결 명령 (Connector 사용) --- #
                case 'CONNECT':
                    self.connector.connect()
                    success = True
                    msg = f"TwinCAT 연결 성공 ({self.connector.ams_net_id})"


                # --- 이동 명령 (Commander 사용) --- #
                case 'MOVE':
                    fanuc_data = self._transform_to_fanuc_format(self.data)

                    # Commander 호출
                    # FanucAdapter.run_legacy_sequence (bool, str)을 반환하므로 그대로 받음
                    success, msg = self.commander.run_legacy_sequence(
                        fanuc_data, 
                        check_stop_func=self._is_interrupted
                    )

                    success = True
                    msg = "단일 좌표 이동 완료"


                # --- 제어 명령 (Commander 사용) --- #
                case 'START':
                    success, msg = self.commander.start_sequence_plc_signals()
                case 'STOP':
                    success, msg = self.commander.end_sequence_plc_signals()
                case _:
                    msg = "알 수 없는 명령입니다."
                    pass

        # -----------------------------------------------------------
        # 예외 처리 (로그는 Service가 남기므로 여기선 실패 사유만 전달)
        # -----------------------------------------------------------
        except InterruptedError:
            success = False
            msg = "작업이 사용자에 의해 중단됨"

        except Exception as e:
            success = False
            msg = f"작업중 오류 발생: {e}"


        # 결과 보고 및 종료
        self.result.emit(success, msg)
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

    def _transform_to_fanuc_format(self, data: Any) -> List[Dict]:
        """
        UNIFIED_DATA 데이터를 FANUC_SCHEMA 형식으로 변환
        """

        # 입력 데이터 정규화 - List로 만들기
        if isinstance(data, dict):
            source_list = [data]
        elif isinstance(data, list):
            source_list = data
        else:
            # None이거나 엉뚱한 타입이 오면 에러 발생
            raise ValueError(f"MOVE 데이터는 dict 또는 list여야 합니다. (받은 타입: {type(data)})")


        # 데이터 변환 (소문자 -> 대문자 매핑)
        transformed_list = []

        # source_list를 순회하는 루프
        for item in source_list:

            converted_item = {}
            
            # FANUC_SCHEMA에 정의된 대로 데이터를 뽑아냄
            for fanuc_key, info in FANUC_SCHEMA.items():
                
                unified_key = info['source'] # 'feed', 'x'...
                target_type = info['type']   # float
                
                # 값 가져오기 (기본값 0.0)
                val = item.get(unified_key, 0.0)
                
                # 타입 강제 변환 (안전장치)
                try:
                    converted_item[fanuc_key] = target_type(val)
                except (ValueError, TypeError):
                    converted_item[fanuc_key] = target_type() # 0.0

            transformed_list.append(converted_item)

        return transformed_list