# demo_service.py
# import magic
import mimetypes
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject, QThread
from .demo_worker import FileLoadWorker
from .demo_logger import logger



class FileService(QObject):
    """시퀀스 처리 서비스 클래스"""

    # 시그널 - 뷰모델이 구독
    sequence_data_from_file = pyqtSignal(dict)
    


    def __init__(self):
        super().__init__()

        # 비서(Worker) 직군 '정원 확보'
        self.file_worker: FileLoadWorker | None = None

        # 새로운 사무실(QThread) '공간 확보'
        self.file_thread: QThread | None = None


    def load_file(self, file_path: Path):
        """파일 읽기"""

        if self.file_thread:  # 이미 작업 중이면 무시
            return
        
        # 읽어 온 파일 종류 파악(csv, txt)
        file_type = self._detact_file_type(file_path)


        # 사무실 계약
        self.file_thread = QThread()
        # 순수 QObject, 스레드 세이프
        self.file_worker = FileLoadWorker(file_path, file_type)
        # 비서를 새 사무실로 전근 발령
        self.file_worker.moveToThread(self.file_thread)


        # 작업 결과 시그널 예약
        self.file_worker.file_loaded.connect(self._handle_file_loaded)


        # 스레드 정리
        self.file_worker.finished.connect(
            lambda: self._cleanup(self.file_thread, self.file_worker)
        )        


        # 스레드 시작
        self.file_thread.start()

        # 스레드 시작 및 작업 실행 - 이벤트 큐를 통해 워커의 run 메서드 호출
        QMetaObject.invokeMethod(self.file_worker, "run", Qt.ConnectionType.QueuedConnection)




    @pyqtSlot(bool, str, dict)
    def _handle_file_loaded(self, result: bool, status_msg: str, sequence_data: dict):
        """파일 로드 작업 완료 시 Worker로부터 보고받음"""

        # print("\n워커에서 작업 끝나서 서비스 레이어에 예약된 시그널 호출됨: _handle_file_loaded")
        # print(f"\n결과:{result}\n메시지:{status_msg}\n데이터:{sequence_data}")

        if result:
            logger.info(status_msg)
            self.sequence_data_from_file.emit(sequence_data)
            # print(f"워커->서비스에서 emit->뷰모델이구독: {sequence_data}\n파일타입{type(sequence_data)}")

        elif not result:
            logger.error(status_msg)
            # self.log_updated.emit(status_msg)
            # self.connection_changed.emit(result, status_msg)

        # logger.info(status_msg)
        # self.log_updated.emit(status_msg)
        # self.connection_changed.emit(success, status_msg)



    def _detact_file_type(self, file_path: Path) -> str:
        """csv, txt 중 파일 종류가 무엇인지 판단"""

        # mimetype 구하기 (tuple: (type, encoding))
        mime_type, encoding = mimetypes.guess_type(str(file_path))

        if mime_type == 'text/csv':
            return 'csv'
        elif mime_type == 'text/plain':
            return 'txt'
        
        # mimetype 으로 판단되지 않을 때는 확장자 검사로 찾아내기
        file_suffix = file_path.suffix.lower()

        if file_suffix == '.txt':
            return 'txt'
        elif file_suffix == '.csv':
            return 'csv'

        else:
            # 파일 형태를 끝까지 못 찾아낸다면
            logger.warning(f"지원하지 않는 파일 형식입니다: {file_path}")
            raise ValueError(f"지원하지 않는 파일 형식입니다: {file_path}")




    @pyqtSlot()
    def _cleanup(self, thread: QThread | None = None, worker: QObject | None = None):
        """Worker와 Thread 안전하게 정리"""
        if thread and thread.isRunning():
            thread.quit()
            thread.wait(3000)

        if worker:
            worker.deleteLater()
            worker = None
