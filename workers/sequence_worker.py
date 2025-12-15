# view_models/sequence_worker.py
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from models.sequence_model import SequenceModel
from utils.file_handler import load_text, load_csv
from parsers.sequence_parser import SequenceParserManager
from core.event_bus import EVENT_BUS



class SequenceWorker(QObject):
    """
    Model(순수로직/함수)을 불러서 일 시킴

    스레드 :  백그라운드 스레드

    서비스 레이어는 나에게 일을 시키고 UI 스레드로 복귀 - 앱 멈춤 없다
    """

    # 로컬 시그널 (Service가 구독)
    result = pyqtSignal(bool, str, dict)    # 작업 결과 알림(성공여부, 메시지, 읽은 데이터)
    finished = pyqtSignal()                 # 작업 종료 알림


    def __init__(self, file_path: Path):
        super().__init__()

        # 로그 메세지의 말머리(로그 발생 위치 표시)
        self._log_prefix = f"[{self.__class__.__name__}]"

        self._file_path = file_path

        # Model 인스턴스
        self.model = SequenceModel()


    def run(self):
        """시간이 오래 걸리는 비동기 작업(시퀀스 파일 읽기)을 수행"""

        file_data = None

        # --- 파일 읽기 --- #
        try:
            file_data = load_csv(self._file_path)

        except Exception as e:
            error_msg = f"{self._log_prefix} 파일({self._file_path}) 읽기 실패: {e}"

            # 에러 로그 '방송'
            EVENT_BUS.log.message.emit(error_msg, "ERROR")

            # 파일 읽기 실패 '보고'
            self.result.emit(False, error_msg, {})

            # 스레드 종료 신호
            self.finished.emit()


        # --- 읽은 데이터 파싱 --- #
        try:
            parsed_data = self._parse_data(self._file_path, file_data)

            # 파싱 성공 '보고'
            msg = f"{self._log_prefix} 파일({self._file_path}) 파싱 완료"
            self.result.emit(True, msg, parsed_data)

        except Exception as e:
            error_msg = f"{self._log_prefix} 파일({self._file_path}) 파싱 실패: {e}"

            # 에러 로그 '방송'
            EVENT_BUS.log.message.emit(error_msg, "ERROR")

            # 파싱 실패 '보고'
            self.result.emit(False, error_msg, {})

        finally:
            # 결과 상관 없이 스레드 종료 신호
            self.finished.emit()



    def _parse_data(self, file_path: Path, raw_data) -> dict:
        """
        파일 경로에 맞는 파서를 찾아서 Raw 데이터를 파싱하는 헬퍼 메서드

        파싱을 서비스 레이어가 아닌 워커 레이어에서 수행하는 이유:
            Service 레이어는 보통 메인 스레드(UI 스레드)에서 동작한다
            만약 10만줄짜리 데이터를 서비스 레이어에서 파싱 한다면 그 동안 UI가 멈춤
            ∴ CPU를 많이 사용하는 파싱 작업은 백그라운드 스레드(Worker)에서 처리해야 됨
        """

        # 파서 매니저 객체 생성
        parser_manager = SequenceParserManager()
        
        # 파일 경로에 맞는 파서 객체를 찾기
        parser = parser_manager.find_parser(file_path)

        return parser.parse(raw_data)

