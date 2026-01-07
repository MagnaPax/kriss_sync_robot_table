# view_models/waypoints_viewmodel.py
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS
from typing import List, Dict, Any

class WaypointsViewModel(QObject):
    """WaypointsWidget의 상태 및 비즈니스 로직을 관리하는 뷰모델"""

    # 로컬 시그널 (뷰가 구독)    
    waypoints_data_changed = pyqtSignal(list)   # 데이터 갱신
    clear_waypoints = pyqtSignal()              # 화면 초기화
    

    def __init__(self):
        super().__init__()
        self._log_prefix = f"[{self.__class__.__name__}]"

        # EventBus 구독
        EVENT_BUS.data.sequence_data_loaded.connect(self._on_sequence_data_loaded)  # 시퀀스 데이터 로드 완료 방송
        EVENT_BUS.control.clear_view_content.connect(self._on_clear_requested)      # 현재 화면에 표시된 콘텐츠 초기화

    @pyqtSlot(list)
    def _on_sequence_data_loaded(self, data: List[Dict[str, Any]]):
        """데이터 로드 시 View에게 전달"""
        self.waypoints_data_changed.emit(data)

    @pyqtSlot(str)
    def _on_clear_requested(self, scope: str):
        """Waypoints 지우는게 맞을때만 View에게 알림"""
        if scope in ["waypoints", "all"]:
            self.clear_waypoints.emit()
