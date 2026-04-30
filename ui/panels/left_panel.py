# ui/panels/left_panel.py
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget
from typing import TYPE_CHECKING, Optional
from ui.widgets.logo_widget import LogoWidget
from ui.widgets.turntable_gauge import TurntableGaugeWidget
from ui.widgets.servo_controller_widget import ServoControllerWidget
from ui.widgets.robot_controller_widget import RobotControllerWidget

# 순환 참조 방지용
if TYPE_CHECKING:
    from view_models.main_window_viewmodel import MainViewModel


class LeftPanel(QFrame):
    def __init__(self, view_model: "MainViewModel", parent: Optional[QWidget] = None):    # 부모가 없을 수도 있다(독립적 테스트 가능)
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
        self.turntable_gauge = TurntableGaugeWidget()
        servo_control = ServoControllerWidget()
        target_position = RobotControllerWidget()


        # --- 뷰모델 주입 --- #
        # MainViewModel에서 뷰모델을 꺼내서 주입
        servo_control.set_view_model(self.vm.servo_controller_vm)
        target_position.set_view_model(self.vm.robot_controller_vm)
        self.turntable_gauge.set_view_model(self.vm.turntable_gauge_vm)



        # 바탕 레이아웃에 위젯 추가
        main_layout.addWidget(self.logo_widget,      stretch=5)
        main_layout.addWidget(self.turntable_gauge,  stretch=20)
        main_layout.addWidget(target_position,   stretch=40)
        main_layout.addWidget(servo_control,     stretch=35)
