# services/sequence_service.py
from pathlib import Path
from typing import List, Dict, Any
from core.event_bus import EVENT_BUS
from workers.sequence_worker import SequenceWorker
from PyQt6.QtCore import QObject, QThread





class SequenceService(QObject):
    """
    스레드 : 메인 스레드(UI 스레드)
    역할:
        워커 스레드 관리
    """

    def __init__(self):
        super().__init__()

        self._log_prefix = f"[{self.__class__.__name__}]"

        # 읽어 온 시퀀스 데이터 보관 
        self._sequence_data: List[Dict[str, Any]] = []

        # 새로운 사무실(QThread) '공간 확보'
        self._thread: QThread | None = None

        # 비서(Worker) 직군 '정원 확보'
        self._worker: SequenceWorker | None = None        


    def load_sequence_file(self, file_path: Path):
        """
        시퀀스 파일의 데이터를 읽기
        """

        if self._thread and self._thread.isRunning():
            EVENT_BUS.log.message.emit("이전 작업이 아직 진행중입니다", "WARNING")
            return # 이전 작업이 있다면 중복 실행 방지

        # csv 파일이 맞는지 확인
        self._is_csv(file_path)

        # 사무실 계약
        self._thread = QThread()

        # 비서(Worker) 채용
        self._worker = SequenceWorker(file_path)

        # 비서를 새 사무실로 전근 발령 - moveToThread() : 스레드 소속 변경
        self._worker.moveToThread(self._thread)

        # 비서의 전화보고(emit)를 받고 어떻게 처리(Slot)할지 미리 정해놓기(connect)
        self._worker.result.connect(self._handle_file_load_result)
        self._worker.finished.connect(self._cleanup)

        # --- 사무실(Thread)에서 벌어질 이벤트 예약(connect) ---
        # 사무실 문 열리면 비서에게 '일 시작해라' 지시
        self._thread.started.connect(self._worker.run)
        # 사무실이 문 닫히면 → 사무실 정리하고 폐기하도록 예약
        self._thread.finished.connect(self._thread.deleteLater)


        # 사무실 오픈(스레드 시작)
        # 사무실 문을 열고 내부 이벤트 루프를 가동하는 것
        self._thread.start()




    def _is_csv(self, file_path: Path) -> None:

        if file_path.suffix.lower() != '.csv':
            msg = f"{self._log_prefix} csv 파일이 아닙니다: {file_path}"
            EVENT_BUS.log.message.emit(f"{msg}", "ERROR")
            raise ValueError(msg)


    @pyqtSlot(bool, str, dict) # type: ignore
    def _handle_file_load_result(self, success: bool, msg: str, sequence_data: Dict[str, Any]):
        """
        워커가 실행한 파일 읽기 결과 처리
            워커의 결과물 결과물(dict)을 앱에서 쓸 수 있는 형태(list)로 가공하여 방송
        """

        # 상태 로그 방송
        level = "INFO" if success else "ERROR"
        EVENT_BUS.log.message.emit(msg, level)

        if success:
            # 딕셔너리 -> 리스트 (값만 추출)
            # data.values()를 통해 순서가 있는 리스트로 만듦
            sequence_list = list(sequence_data.values())

            # 데이터 보관 - 나중에 누가 달라고 할 때를 대비
            self._sequence_data = sequence_list

            # 시퀀스 데이터를 방송으로 송출
            #   "데이터 준비됐습니다~ 필요한 분들 가져다 쓰세요"
            EVENT_BUS.data.sequence_data_loaded.emit(sequence_list)
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 시퀀스 파일 -> 데이터 처리 완료: {len(sequence_list)}건", "INFO")


    @pyqtSlot() # type: ignore
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
