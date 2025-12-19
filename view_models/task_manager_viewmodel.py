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
    busy_state_changed = pyqtSignal(dict)               # 로봇과 턴테이블의 busy 상태
    runtime_updated = pyqtSignal(str)                   # 런타임 시간 업데이트


    def __init__(self, sequence_service: SequenceService):
        super().__init__()

        # 로그 메세지의 말머리(로그 발생 위치 표시)
        self._log_prefix = f"[{self.__class__.__name__}]"

        # 서비스 객체 생성
        self._sequence_service = sequence_service
        self._plc_service = PLCService()

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
        # 시퀀스 데이터
        EVENT_BUS.data.sequence_data_loaded.connect(self._on_sequence_data_updated)
        # 진행 상황 모니터링 (작업 끝났는지 감시용)
        EVENT_BUS.data.progress_updated.connect(self._check_sequence_finished)
        # '바쁨 상태' 방송이 오면 -> 내 로컬 시그널(busy_state_changed)로 바로 재방송
        #   TaskManagerWidget.update_data와 연결
        EVENT_BUS.data.device_busy_status.connect(self.busy_state_changed.emit)


    def load_sequence_data(self, file_path: Path):
        """View의 LOAD 버튼 클릭 이벤트 처리"""
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 시퀀스 데이터 읽기 시작", "DEBUG")

        # 새 파일을 열면 런타임 초기화
        self._reset_runtime_timer()

        # Service에게 파일 읽기 시킨다
        self._sequence_service.load_sequence_file(file_path)


    def start_sequence(self):
        """
        START 버튼 클릭 시
            작업 시작 (전체 시퀀스 데이터를 실어서 보냄)
        """

        # 방어코드
        if not self._cached_sequence_data: return

        # 런타임 시작
        self._runtime_timer.start()

        EVENT_BUS.log.message.emit(f"{self._log_prefix} 시퀀스 시작 (데이터 {len(self._cached_sequence_data)}건)", "INFO")
        
        # 전체 데이터 전송 (시퀀스 처음부터 실행)
        self._plc_service.process_sequence_data(self._cached_sequence_data)

    def stop_sequence(self):
        """STOP 버튼 클릭 시"""
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 시퀀스 중지 요청", "INFO")

        # 타이머 일시정지
        self._runtime_timer.stop()

        # PLCService 한테도 멈추라고 명령
        self._plc_service.stop_process()

    def is_system_busy(self) -> bool:
        """
        시스템(PLC/로봇)이 현재 작업 중인지 체크
        Return:
            True: 작업 중
            False: 대기 중
        """
        return self._plc_service.is_running

    def _reset_runtime_timer(self):
        self._elapsed_seconds = 0
        self.runtime_updated.emit("00 : 00 : 00")


    # --- 슬롯 메서드 --- #
    @pyqtSlot(list)
    def _on_sequence_data_updated(self, data: list):
        """Event Bus를 통해 온 시퀀스 데이터를 캐싱"""
        self._cached_sequence_data = data

    @pyqtSlot()
    def _on_runtime_tick(self):
        """1초마다 실행되어 시간을 1씩 늘리고 방송"""
        self._elapsed_seconds += 1

        # 초 -> 시:분:초 문자열 변환
        # divmod(나눌 수, 나누는 수) -> (몫, 나머지) 반환
        minutes, seconds = divmod(self._elapsed_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        runtime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # 방송 - UI야, 이 글자로 바꿔라
        self.runtime_updated.emit(runtime_str)


    @pyqtSlot(int, int, str)
    def _check_sequence_finished(self, current_step, total_steps, status):
        """진행 상황을 감시하다가 끝났으면 타이머 정지"""

        # 마지막 스텝이고 + 상태가 '처리완료(processed)'라면
        if current_step == total_steps and status == "processed":
            # 타이머 정지
            self._runtime_timer.stop()
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 모든 시퀀스 작업 완료 (총 {total_steps}개의 데이터)", "INFO")
