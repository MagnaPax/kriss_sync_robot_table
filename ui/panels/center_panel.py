# ui/panels/center_panel.py
from typing import TYPE_CHECKING, Optional
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget
from ui.widgets.world_coordinates_widget import WorldCoordinatesWidget
from ui.widgets.user_coordinates_widget import UserCoordinatesWidget
from ui.widgets.emergency_stop_widget import EmergencyStopWidget

# 순환 참조 방지용
if TYPE_CHECKING:
    from view_models.main_window_viewmodel import MainViewModel


class CenterPanel(QFrame):
    def __init__(self, view_model: "MainViewModel", parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.vm = view_model  # 메인 뷰모델 저장 (필요 시 사용)

        self.setObjectName("center_panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)    # OS/Qt 테마 스타일을 따라감
        self.setFrameShadow(QFrame.Shadow.Sunken)       # 음영이 아래쪽에 있어, 패널이 눌려 보임

        # 레이아웃 설정
        layout = QVBoxLayout(self)

        world_coordinates = WorldCoordinatesWidget()
        user_position = UserCoordinatesWidget()
        emergency_stop = EmergencyStopWidget()


        # --- 뷰모델 주입 --- #
        # MainViewModel에서 뷰모델을 꺼내서 주입
        world_coordinates.set_view_model(self.vm.world_coordinates_vm)
        user_position.set_view_model(self.vm.user_coordinates_vm)
        emergency_stop.set_view_model(self.vm)


        # 바탕 레이아웃에 위젯 추가
        layout.addWidget(emergency_stop,    stretch=1)
        layout.addWidget(world_coordinates, stretch=49)  
        layout.addWidget(user_position,     stretch=50)
