# ui/panels/left_panel.py
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QGroupBox
from typing import TYPE_CHECKING
from ..widgets import LogoWidget
from ..widgets import TurntableWidget
from ..widgets import CurrentStateWidget
from ui.widgets.servo_control_widget import ServoControlWidget

if TYPE_CHECKING:
    from view_models.main_window_viewmodel import MainViewModel



class LeftPanel(QFrame):
    def __init__(self, view_model: "MainViewModel", parent=None):    # 부모가 없을 수도 있다(독립적 테스트 가능)
        super().__init__(parent)

        # 뷰모델 저장 (나중에 자식 위젯들이 데이터 필요할 때 여기서 꺼내 줌)
        self.vm = view_model

        self.setObjectName("left_panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)    # 프레임의 기본 형태 설정
        self.setFrameShadow(QFrame.Shadow.Sunken)       # 프레임의 입체감(빛, 음영) 설정

        # 수직 레이아웃
        main_layout = QVBoxLayout(self)

        # 위젯들
        self.logo_widget = LogoWidget()
        servo_control = ServoControlWidget()

        # --- 뷰모델 주입 --- #
        # MainViewModel에서 뷰모델을 꺼내서 주입
        servo_control.set_view_model(self.vm.servo_control_vm)

        
        # --- TurntableWidget을 QGroupBox 안에 넣기 ---
        turntable_group = QGroupBox("1️⃣ Turntable Angle")  # QGroupBox 생성
        turntable_layout = QVBoxLayout(turntable_group)     # GroupBox에 적용할 레이아웃 생성
        turntable_widget = TurntableWidget()                # 실제 위젯 인스턴스 생성
        # 위젯 위아래로 공간(stretch)을 추가하여 수직 중앙 정렬
        turntable_layout.addStretch(1)
        turntable_layout.addWidget(turntable_widget)
        turntable_layout.addStretch(1)


        # --- CurrentStateWidget을 QGroupBox 안에 넣기 ---
        current_state_group = QGroupBox("Current State")
        current_state_layout = QVBoxLayout(current_state_group)
        current_state_widget = CurrentStateWidget()
        current_state_layout.addStretch(1)
        current_state_layout.addWidget(current_state_widget)
        current_state_layout.addStretch(1)


        turntable_group.setStyleSheet("color: black; border: 1px solid red;")
        current_state_group.setStyleSheet("color: black; border: 1px solid black;")


        # 바탕 레이아웃에 위젯 추가
        main_layout.addWidget(self.logo_widget,  stretch=1)     # 1/5 -> 20%
        main_layout.addWidget(turntable_group,   stretch=2)     # 2/5 -> 40%
        main_layout.addWidget(current_state_group, stretch=1)   # 1/5 -> 20%
        main_layout.addWidget(servo_control,    stretch=1)      # 1/5 -> 20%
