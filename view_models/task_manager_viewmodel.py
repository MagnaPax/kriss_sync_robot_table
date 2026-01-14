# view_models/task_manager_viewmodel.py
"""
- UI 의 상태 관리
- UI 의 이벤트 처리
- 명령 및 로직 요청
"""
from pathlib import Path
from typing import TYPE_CHECKING, List, Dict, Any
from core.event_bus import EVENT_BUS
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer

if TYPE_CHECKING:
    from services.sequence_service import SequenceService
    from services.plc_service import PLCService



class TaskManagerViewModel(QObject):

    # View에게 상태를 알리는 시그널
    sequence_data_loaded_complete = pyqtSignal(dict)    # 파일 읽기 성공
    sequence_data_loaded_failed = pyqtSignal(str)       # 파일 읽기 실패
    busy_state_changed = pyqtSignal(dict)               # 로봇과 턴테이블의 busy 상태
    runtime_updated = pyqtSignal(str)                   # 런타임 시간 업데이트
    sequence_execution_active = pyqtSignal(bool)         # 시퀀스가 실행 중인지 아닌지


    def __init__(self, sequence_service: "SequenceService", plc_service: "PLCService"):
        super().__init__()

        # 로그 메세지의 말머리(로그 발생 위치 표시)
        self._log_prefix = f"[{self.__class__.__name__}]"

        # 서비스 객체 생성
        self._sequence_service = sequence_service
        self._plc_service = plc_service

        # 시퀀스 데이터 캐싱 변수
        self._cached_sequence_data = None

        # --- 런타임 --- #
        # 변수 생성
        self._elapsed_seconds = 0   # 경과 시간 (초)
        # 타이머 설정
        self._runtime_timer = QTimer()
        self._runtime_timer.setInterval(1000)  # 1초
        self._runtime_timer.timeout.connect(self._on_runtime_tick)

        # --- 시그널 구독 --- #
        # 시퀀스 데이터 읽기 완료
        EVENT_BUS.data.sequence_data_loaded.connect(self._on_sequence_data_updated)
        # '바쁨 상태' 방송이 오면 -> 내 로컬 시그널(busy_state_changed)로 바로 재방송
        #   TaskManagerWidget.update_data와 연결
        EVENT_BUS.data.servo_busy_status.connect(self.busy_state_changed.emit)
        # 전체 시퀀스 작업(Job) 종료 시그널 연결
        EVENT_BUS.data.sequence_job_finished.connect(self._on_sequence_job_finished)


    def load_sequence_data(self, file_path: Path):
        """View의 LOAD 버튼 클릭 이벤트 처리"""
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 시퀀스 데이터 읽기 시작", "DEBUG")

        # 새 파일을 열면 런타임 초기화
        self._reset_runtime_timer()
        
        # [UX] 파일 읽기 시작 알림 방송
        EVENT_BUS.system.loading_started.emit("파일 읽는 중...")

        # 이전에 표시된 Waypoints 콘텐츠 초기화 시그널 방송
        EVENT_BUS.control.clear_view_content.emit("waypoints")

        # 파일 경로가 잘못되었거나 형식이 깨졌을 때 에러가 올라올 수 있으므로 try-except로 처리
        try:
            # Service에게 파일 읽기 시킨다 (파일 읽기 실패 시 에러가 올라올 수 있음)
            self._sequence_service.load_sequence_file(file_path)
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 파일 로드 실패: {e}", "ERROR")
            self.sequence_data_loaded_failed.emit(str(e))


    def start_sequence(self):
        """
        START 버튼 클릭 시
            작업 시작 (전체 시퀀스 데이터를 실어서 보냄)
        """

        # 방어코드
        if not self._cached_sequence_data: return

        # 런타임 시작
        self._runtime_timer.start()

        # 시퀀스 실행 중 상태 알림 (버튼 비활성화 등에 사용)
        self.sequence_execution_active.emit(True)
        EVENT_BUS.data.sequence_in_progress.emit("is_sequence_in_progress", True)

        # PLC 서비스가 준비되지 않았는데 시작 명령을 내리면 에러가 날 수 있으므로 try-except로 처리
        try:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 시퀀스 시작 (데이터 {len(self._cached_sequence_data)}건)", "INFO")
            
            # 전체 데이터 전송 (시퀀스 처음부터 실행) - PLC 서비스 호출
            self._plc_service.process_sequence_data(self._cached_sequence_data)
        except Exception as e:
            self._runtime_timer.stop() # 에러 나면 타이머도 멈춤
            self.sequence_execution_active.emit(False) # 실행중 상태 알림
            EVENT_BUS.data.sequence_in_progress.emit("is_sequence_in_progress", False)
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 시퀀스 시작 실패: {e}", "ERROR")

    def stop_sequence(self):
        """STOP 버튼 클릭 시"""
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 시퀀스 중지 요청", "INFO")

        # 타이머 일시정지
        self._runtime_timer.stop()
        
        # 실행 상태 해제 (버튼 활성화에 사용)
        self.sequence_execution_active.emit(False)
        EVENT_BUS.data.sequence_in_progress.emit("is_sequence_in_progress", False)

        # PLCService 한테도 멈추라고 명령
        self._plc_service.stop_process()

    def _reset_runtime_timer(self):
        self._elapsed_seconds = 0
        self.runtime_updated.emit("00 : 00 : 00")


    # --- 슬롯 메서드 --- #
    @pyqtSlot(list)
    def _on_sequence_data_updated(self, data: List[Dict[str, Any]]):
        """Event Bus를 통해 온 시퀀스 데이터를 캐싱"""
        self._cached_sequence_data = data

    @pyqtSlot()
    def _on_runtime_tick(self):
        """
        시간을 1씩 늘리고 방송
            단순히 눈에 보이는 타이머 역할이기 때문에 VM에서 구현
            이 런타임 시간을 로그에 남기는 등의 확장된 기능을 해야 된다면 여기 있으면 안됨
        """
        self._elapsed_seconds += 1

        # 초 -> 시:분:초 문자열 변환
        # divmod(나눌 수, 나누는 수) -> (몫, 나머지) 반환
        minutes, seconds = divmod(self._elapsed_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        runtime_str = f"{hours:02d} : {minutes:02d} : {seconds:02d}"

        # 방송 - UI야, 이 글자로 바꿔라
        self.runtime_updated.emit(runtime_str)


    @pyqtSlot()
    def _on_sequence_job_finished(self):
        """[중요] 시퀀스 작업(Job)이 실제 종료되었을 때 (성공/실패/중단)"""
        # 타이머 정지
        if self._runtime_timer.isActive():
            self._runtime_timer.stop()
        
        # 실행 모드 해제 (버튼 활성화 등에 사용)
        self.sequence_execution_active.emit(False)
        EVENT_BUS.data.sequence_in_progress.emit("is_sequence_in_progress", False)
        total_count = len(self._cached_sequence_data) if self._cached_sequence_data else 0
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 모든 시퀀스 작업 완료 (총 {total_count}개의 데이터)", "INFO")
