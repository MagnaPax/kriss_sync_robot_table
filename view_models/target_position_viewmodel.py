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
from ui.dialogs.macro_settings_dialog import MacroSettingsDialog



class TargetPositionViewModel(QObject):

    # 노출할 시그널 (View 의 메서드가 구독)
    state_changed = pyqtSignal(str)


    def __init__(self, model: Model):
        super().__init__()

        # ViewModel이 Model 인스턴스를 소유한다
        self.model = model

        # 비서(Worker) 직군 '정원 확보'
        self.worker: Worker | None = None

        # 새로운 사무실(QThread) '공간 확보'
        self.worker_thread: QThread | None = None


    @pyqtSlot()
    def open_macro_settings_dialog(self):
        """'Edit Macro' 버튼 클릭 시 View로부터 요청받아 다이얼로그를 연다."""
        dialog = MacroSettingsDialog() # 부모를 지정하지 않으면 독립적인 창으로 뜸
        dialog.exec()   # Modal(호출부 입력 막힘)로 열기

    def start_task(self):
        """시간이 많이 드는 동기 작업(직접 호출 대신 워커 사용)"""
        # 워커 생성
        worker = Worker(self.model)     # 원래 UI 스레드에서 근무
        self._run_async_task(worker)

    def another_task(self):
        """워커의 다른 작업 예제"""
        # worker = AnotherWorker(self.model)
        # self._run_async_task(worker)


    def _run_async_task(self, worker: Worker):
        """비동기 Worker 실행을 위한 헬퍼 메서드"""

        ##############################
        # --- 비서와 사무실 준비 --- #
        ##############################

        # 비서(Worker) 채용
        self.worker = worker    # 파리미터로 받은 worker를 이 클래스의 멤버로 등록

        # 사무실 계약
        self.worker_thread = QThread()

        # 비서를 새 사무실로 전근 발령
        # moveToThread() : 스레드 소속 변경
        self.worker.moveToThread(self.worker_thread)


        #################################
        # --- 비서가 해야할 일 예약 --- #
        #################################
        # connect : 예약
        # start : 실행
        # '비서'가 방출(emit)하는 각각의 시그널에 맞는 Slot 처리 "예약"

        # 작업 결과 시그널 연결(예약)
        self.worker.task_completed.connect(self.on_task_done)
        self.worker.task_failed.connect(self.on_task_failed)

        # 정리
        self.worker.finished.connect(self._cleanup_worker)


        ##########################
        # --- 비서 근무 시작 --- #
        ##########################
        # 사무실 개업 (스레드 "시작")
        self.worker_thread.start()

        # 스레드 실행 및 작업 실행 - 이벤트 큐를 통해 워커의 run 메서드 호출
        QMetaObject.invokeMethod(
            self.worker,
            "run",
            Qt.ConnectionType.QueuedConnection
        )

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
        """Worker와 Thread 안전하게 정리"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(3000)

        if self.worker:
            self.worker.deleteLater()
            self.worker = None