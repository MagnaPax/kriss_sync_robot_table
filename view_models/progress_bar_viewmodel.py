from typing import List, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS

class ProgressBarViewModel(QObject):
    # 로컬 시그널 - UI 업데이트를 위해 View가 구독
    progress_range_changed = pyqtSignal(int, int)    # 최소값, 최대값
    progress_value_changed = pyqtSignal(int)         # 현재 값
    progress_status_changed = pyqtSignal(str)   # 상태 메시지

    def __init__(self):
        super().__init__()
        self._log_prefix = f"[{self.__class__.__name__}]"

        # EventBus 시그널 연결
        EVENT_BUS.data.sequence_data_loaded.connect(self._on_sequence_data_loaded)  # 시퀀스 데이터 로드 시
        EVENT_BUS.data.progress_updated.connect(self._on_progress_updated)            # 진행률 업데이트 시
        
    @pyqtSlot(list)
    def _on_sequence_data_loaded(self, data: List[Dict[str, Any]]):
        """시퀀스 데이터가 로드되면 프로그레스바 범위를 설정"""
        total_count = len(data)
        self.progress_range_changed.emit(0, total_count)
        self.progress_value_changed.emit(0)
        self.progress_status_changed.emit(f"Ready ({total_count} items)")

    @pyqtSlot(int, int, str)
    def _on_progress_updated(self, current: int, total: int, status: str):
        """진행률 업데이트 처리"""
        self.progress_value_changed.emit(current)
        self.progress_status_changed.emit(f"{current} / {total}")
