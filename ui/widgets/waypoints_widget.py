# ui/widgets/waypoints_widget.py

from typing import Any
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QLabel

from ui.widgets.base_widget import BaseWidget
from core.event_bus import EVENT_BUS


class WaypointsWidget(BaseWidget):
    """
    웨이포인트 목록을 표시하고 관리하는 위젯
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_prefix = f"[{self.__class__.__name__}]"
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 초기화", "DEBUG")

    def _init_ui(self):
        """
        UI 초기화
        """
        self.setObjectName("waypoints_widget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel("웨이포인트 목록 (구현 예정)")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    def update_data(self, data: Any):
        """
        로봇과 턴테이블이 이동해야 될 경로점들의 데이터를 받아와서 UI를 업데이트한다.
        """
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 데이터 업데이트: {data}", "DEBUG")
        # TODO: 실제 웨이포인트 데이터를 받아와서 UI를 업데이트하는 로직 구현
        pass

    def clear_widget(self):
        """
        위젯 초기화
        """
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 위젯 초기화", "DEBUG")
        # TODO: 웨이포인트 목록을 지우는 로직 구현
        super().clear_widget()
