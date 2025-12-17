# view_models/task_manager_viewmodel.py
"""
- UI 의 상태 관리
- UI 의 이벤트 처리
- 명령 및 로직 요청
"""
from pathlib import Path
from core.event_bus import EVENT_BUS
from services.plc_service import PLCService
from services.sequence_service import SequenceService
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer



class TaskManagerViewModel(QObject):

    # View에게 상태를 알리는 시그널
    sequence_data_loaded_complete = pyqtSignal(dict)    # 파일 읽기 성공
    sequence_data_loaded_failed = pyqtSignal(str)       # 파일 읽기 실패
    device_busy_status = pyqtSignal(dict)               # 로봇과 턴테이블의 busy 상태


    def __init__(self, sequence_service: SequenceService):
        super().__init__()

        # 로그 메세지의 말머리(로그 발생 위치 표시)
        self._log_prefix = f"[{self.__class__.__name__}]"

        # 서비스 객체 생성
        self._sequence_service = sequence_service
        self._plc_service = PLCService()

        # 시퀀스 데이터 시그널 데이터 저장 & 구독
        self._cached_data = None
        EVENT_BUS.data.sequence_data_loaded.connect(self._on_sequence_data_updated)

        # 상태 모니터링 타이머 설정
        self._status_timer = QTimer()
        self._status_timer.setInterval(100)  # 100ms = 0.1초
        self._status_timer.timeout.connect(self._monitoring_loop)
        self._status_timer.start()           # 타이머 시작


    def load_sequence_data(self, file_path: Path):
        """View의 LOAD 버튼 클릭 이벤트 처리"""
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 시퀀스 데이터 읽기 시작", "DEBUG")

        # Service에게 시킴
        self._sequence_service.load_sequence_file(file_path)


    def start_sequence(self):
        """
        View의 START 버튼 클릭 이벤트 처리
            작업 시작 (전체 시퀀스 데이터를 실어서 보냄)
        """

        # 방어코드
        if not self._cached_data: return

        EVENT_BUS.log.message.emit(f"{self._log_prefix} 시퀀스 실행 요청 (데이터 {len(self._cached_data)}건)", "INFO")
        
        self._plc_service.process_sequence_data(self._cached_data)


    def is_system_busy(self) -> bool:
        """
        시스템(PLC/로봇)이 현재 작업 중인지 체크
        Return:
            True: 작업 중
            False: 대기 중
        """
        return self._plc_service.is_running


    def _monitoring_loop(self):
        """
        0.1초마다 실행됨
        서비스에게 '바쁘냐'고 물어보고 그 결과를 UI로 방송
        """
        # 상태 확인
        is_busy = self._plc_service.is_running
        
        # UI(Widget)가 이해할 수 있는 형태(dict)로 포장
        #   BaseWidget이나 TaskManagerWidget의 update_data는 파라미터로 딕셔너리를 받기 때문
        status_data = {
            'is_busy': is_busy,
            # TODO: 필요하다면 다른 정보도 여기에 추가 가능
            #       'connection': self._plc_service.is_connected
        }

        # 방송
        # TaskManagerWidget.update_data와 연결
        self.device_busy_status.emit(status_data)


    # --- 슬롯 메서드 --- #
    @pyqtSlot(list)
    def _on_sequence_data_updated(self, data: list):
        """Event Bus를 통해 온 시퀀스 데이터를 캐싱"""
        self._cached_data = data