# view_models/target_position_viewmodel.py
"""
ViewModel

1. View 의 요청을 처리 
    - 하지만 View '존재'는 모른다.

2. Model 의 메서드를 호출
    2.1 만약 Model 의 작업이 오래 걸리면 앱의 freeze를 막기 위해 비동기 처리
        -> Worker 사용(∴ 뷰모델 레이어의 일부)
        -> 동기(Synchronous) 작업(앱이 멈춤)을 대신 할 '비서(Worker)' 생성

        
3. View 에 상태를 보고

View → ViewModel → (Worker) → Model
"""

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot, QMetaObject
from view_models.target_position_viewmodel_worker import TargetPositionViewModelWorker as Worker
from models.position_model import PositionModel as Model
from services.plc_service import PLCService



class TargetPositionViewModel(QObject):

    # 로컬 시그널 (View 의 메서드가 구독)
    state_changed = pyqtSignal(str)


    def __init__(self, model: Model, plc_service: PLCService):
        """
        인자들:
            model: 데이터 모델 인스턴스
            plc_service: 앱 전역에서 공유되는 PLC 서비스 인스턴스
        """
        super().__init__()

        # ViewModel이 Model 인스턴스를 소유한다
        self._model = model

        self._plc_service = plc_service


        # 비서(Worker) 직군 '정원 확보'
        self._worker: Worker | None = None

        # 새로운 사무실(QThread) '공간 확보'
        self._thread: QThread | None = None


    @pyqtSlot()

    def start_task(self):
        """시간이 많이 드는 동기 작업(직접 호출 대신 워커 사용)"""
        # 워커 생성
        worker = Worker(self._model)     # 원래 UI 스레드에서 근무
        self._run_async_task(worker)

    def another_task(self):
        """워커의 다른 작업 예제"""
        # worker = AnotherWorker(self._model)
        # self._run_async_task(worker)


    def _run_async_task(self, worker: Worker):
        """비동기 Worker 실행을 위한 헬퍼 메서드"""

        # 비서(Worker) 채용
        self._worker = worker    # 파리미터로 받은 worker를 이 클래스의 멤버로 등록

        # 사무실 계약
        self._thread = QThread()

        # 비서를 새 사무실로 전근 발령 - moveToThread() : 스레드 소속 변경
        self._worker.moveToThread(self._thread)


        #################################
        # --- 비서가 해야할 일 예약 --- #
        #################################
        # connect : 예약
        # start : 실행
        # '비서'가 방출(emit)하는 각각의 시그널에 맞는 Slot 처리 "예약"

        # 작업 결과 시그널 연결(예약)
        self._worker.task_completed.connect(self.on_task_done)
        self._worker.task_failed.connect(self.on_task_failed)

        # 정리
        self._worker.finished.connect(self._cleanup_worker)



        # 사무실 오픈(스레드 시작)
        # 사무실 문을 열고 내부 이벤트 루프를 가동하는 것
        self._thread.start()


        # 비서에게 "사무실 열리면 이 일 먼저 처리해" 하고 할 일을 업무상자(이벤트 큐)에 등록
        # 비서가 (그 사무실의 이벤트 루프 안에서) 일을 시작하도록 예약하는 것
        # invokeMethod 추가: 즉시 큐 등록 -> 더 빠르고 안전한 스타트를 보장이라는 뜻
        QMetaObject.invokeMethod(self._worker, "run", Qt.ConnectionType.QueuedConnection)


        # '관리자(ViewModel)'는 UI 스레드로 복귀 (앱 멈춤 없음)
        self.state_changed.emit("시간 오래 걸리는 작업 시작됨...")



    ########################################### 
    # Worker 가 방출하는 시그널에 연결할 Slot들
    ###########################################
    @pyqtSlot(str)
    def on_task_done(self, result: str):
        """(시간이 오래 흐른 뒤)'비서'에게 보고를 받음"""
        # 에러 메세지 emit(state_changed 시그널 사용) -> View가 구독해서 처리
        self.state_changed.emit(result)

    @pyqtSlot(str)
    def on_task_failed(self, error_message: str):
        """'비서'에게 작업 실패 보고를 받음"""
        # 에러 메세지 emit(state_changed 시그널 사용) -> View가 구독해서 처리
        self.state_changed.emit(f"오류 발생: {error_message}")

    @pyqtSlot()
    def _cleanup_worker(self):
        """
        실행 중인 스레드(사무실)와 워커(비서)를
        우아하게 종료하고 메모리 누수 없이 안전하게 폐기하는 함수
        """
        if self._thread and self._thread.isRunning():
            # Thread의 이벤트 루프 종료 요청 - 우아한 종료(남아 있는 이벤트 처리 후 종료)
            self._thread.quit()     # 사무실 닫기
            self._thread.wait(3000) # 사무실이 안전하게 문 닫을 때까지 기다림

        if self._worker:
            self._worker.deleteLater()  # 비서 정리 → Qt의 메모리 관리 시스템에 맡겨서 안전하게 폐기
            self._worker = None         # Python 레벨에서도 비서 레퍼런스 해제(메모리 누수 방지)