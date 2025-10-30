# ui/panels/left_panel.py
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QGroupBox, QSizePolicy
from ..widgets import LogoWidget
from ..widgets import TurntableWidget
from ..widgets import CurrentStateWidget


class LeftPanel(QFrame):
    def __init__(self, parent=None):    # 부모가 없을 수도 있다(독립적 테스트 가능)
        super().__init__(parent)
        self.setObjectName("left_panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)    # 프레임의 기본 형태 설정
        self.setFrameShadow(QFrame.Shadow.Sunken)       # 프레임의 입체감(빛, 음영) 설정

        # 수직 레이아웃
        layout = QVBoxLayout(self)

        # 위젯들
        self.logo_widget = LogoWidget()
        turntable_group = TurntableWidget()
        world_position = QGroupBox("World Position")

        # --- CurrentStateWidget을 QGroupBox 안에 넣기 ---
        
        # 1. "Current State" 제목의 QGroupBox 생성
        current_state_group = QGroupBox("Current State")

        # 2. GroupBox에 적용할 레이아웃 생성
        current_state_layout = QVBoxLayout(current_state_group)

        # 3. 실제 위젯 인스턴스 생성
        current_state_widget = CurrentStateWidget()

        # 4. 위젯 위아래로 신축성 있는 공간(stretch)을 추가하여 수직 중앙 정렬
        current_state_layout.addStretch(1)
        current_state_layout.addWidget(current_state_widget)
        current_state_layout.addStretch(1)

        turntable_group.setStyleSheet("color: black; border: 1px solid red;")
        current_state_group.setStyleSheet("color: black; border: 1px solid black;")
        world_position.setStyleSheet("color: black; border: 1px solid green;")

        # 위젯 추가(레이아웃에 맞춰져 추가됨)
        layout.addWidget(self.logo_widget,  stretch=1)  # 1/5 -> 20%
        layout.addWidget(turntable_group,   stretch=2)  # 2/5 -> 40%
        layout.addWidget(current_state_group, stretch=1)  # 1/5 -> 20%
        layout.addWidget(world_position,    stretch=1)  # 1/5 -> 20%
