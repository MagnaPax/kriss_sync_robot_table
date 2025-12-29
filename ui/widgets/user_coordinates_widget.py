# ui/widgets/user_coordinates.py
from PyQt6.QtWidgets import QGroupBox
from ui.widgets.world_coordinates_widget import WorldCoordinatesWidget
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from view_models.user_coordinates_viewmodel import UserCoordinatesViewModel



class UserCoordinatesWidget(WorldCoordinatesWidget):
    """
    User Coordinates 표시 위젯
    WorldCoordinatesWidget의 UI 구조를 상속받아 재사용하며,
    ViewModel과 데이터 바인딩만 별도로 처리한다.
    """
    
    def __init__(self, parent=None):
        # ViewModel 타입 힌트 재정의를 위해 초기화
        self.viewmodel: Optional["UserCoordinatesViewModel"] = None
        super().__init__(parent)

    def set_view_model(self, view_model: "UserCoordinatesViewModel"): # type: ignore[override]
        """ViewModel 주입 및 이벤트 연결 (Override)"""
        self.viewmodel = view_model
        self._bind_events()

    def _bind_events(self):
        """UserCoordinatesViewModel의 시그널 연결 (Override)"""
        if not self.viewmodel: return
        
        # TODO: UserCoordinatesViewModel에 시그널이 정의되면 연결
        # 예: self.viewmodel.pose_changed.connect(self.safe_update_data)
        pass

    def _init_ui(self):
        """UI 초기화 (부모 클래스 로직 재사용 + 커스터마이징)"""
        # 1. WorldCoordinatesWidget의 UI 구성 로직 실행
        super()._init_ui()
        
        self.setObjectName("user_coordinates_widget")   # QSS ID

        # 2. 그룹박스 제목 변경 ("System Coordinates" -> "User Coordinates")
        # WorldCoordinatesWidget의 레이아웃 구조상 첫 번째 아이템이 그룹박스임
        layout = self.layout()
        if layout and layout.count() > 0:
            item = layout.itemAt(0)
            if item and (widget := item.widget()) and isinstance(widget, QGroupBox):
                widget.setTitle("User Coordinates")
