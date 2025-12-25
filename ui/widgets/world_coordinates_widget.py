# ui/widgets/world_coordinates_widget.py
from PyQt6.QtCore import Qt, pyqtSlot
from typing import TYPE_CHECKING, Optional
from PyQt6.QtWidgets import QVBoxLayout, QGroupBox, QGridLayout, QLabel, QFrame
from ui.widgets.base_widget import BaseWidget
from models.fanuc_pose_model import FANUCPose
from models.servo_pose_model import ServoPose

if TYPE_CHECKING:
    from view_models.world_coordinates_viewmodel import WorldCoordinatesViewModel



class WorldCoordinatesWidget(BaseWidget):
    """
    로봇의 World 좌표(FANUCPose)와 서보 모터 상태(ServoPose)를
    실시간으로 모니터링하는 통합 대시보드 위젯
    """

    def __init__(self, parent=None):
        # --- UI 요소 변수 선언 --- #
        # FANUC Robot Labels
        self.lbl_x = None
        self.lbl_y = None
        self.lbl_z = None
        self.lbl_w = None
        self.lbl_p = None
        self.lbl_r = None

        # Servo Motor Labels
        self.lbl_tool_revolution_rpm = None
        self.lbl_tool_rotation_rpm = None
        self.lbl_turntable_degree = None
        self.lbl_turntable_rpm = None

        # ViewModel 인스턴스를 클래스 속성으로 저장
        # super().__init__() 전에 저장
        self.vm: Optional["WorldCoordinatesViewModel"] = None
        
        # BaseWidget의 __init__()이 _init_ui() 호출 → 실제 UI 생성
        super().__init__(parent)


    def set_view_model(self, view_model: "WorldCoordinatesViewModel"):
        """
        외부에서 뷰모델을 꽂아주는 함수(Setter)
            MainViewModel 이 WorldCoordinatesViewModel 소유
            CenterPanel 에서 WorldCoordinatesWidget 에게 주입
        """
        self.vm = view_model

        # 이벤트 연결(vm이 있을때만 연결되게)
        self._bind_events()


    def _bind_events(self):
        """EventBus 시그널 연결"""
        if not self.vm: return

        # 로봇 위치 변경
        self.vm.robot_pose_changed.connect(self.safe_update_data)

        # 서보 상태 변경
        self.vm.tool_revolution_changed.connect(self._update_tool_revolution_ui)
        self.vm.tool_rotation_changed.connect(self._update_tool_rotation_ui)
        self.vm.turntable_pose_changed.connect(self._update_turntable_ui)


    def _init_ui(self):
        """UI 구성"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setObjectName("world_coordinates_widget")  # 전체 위젯 ID

        # 그룹박스
        group_box = QGroupBox("System Coordinates")

        # 수직 레이아웃
        grid_layout = QVBoxLayout()
        grid_layout.setSpacing(5)    # 섹션간 간격

        # --- 로봇 섹션 --- #
        grid_robot = QGridLayout()
        grid_robot.setHorizontalSpacing(10) # 열 사이 간격
        grid_robot.setVerticalSpacing(5)    # 행 사이 간격
        
        # 레이블 생성 및 초기화
        self.lbl_x = self._create_label()
        self.lbl_y = self._create_label()
        self.lbl_z = self._create_label()
        self.lbl_w = self._create_label()
        self.lbl_p = self._create_label()
        self.lbl_r = self._create_label()

        # 그리드 배치
        robot_rows = [
            (0, "Robot X", self.lbl_x, "mm"),
            (1, "Robot Y", self.lbl_y, "mm"),
            (2, "Robot Z", self.lbl_z, "mm"),
            (3, "Robot W", self.lbl_w, "deg"),
            (4, "Robot P", self.lbl_p, "deg"),
            (5, "Robot R", self.lbl_r, "deg"),
        ]
        self._populate_grid(grid_robot, robot_rows)

        # 그룹박스 레이아웃에 로봇 그리드 추가
        grid_layout.addLayout(grid_robot)

        # --- 구분선 --- #
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        grid_layout.addWidget(line)

        # --- 서보 섹션 --- #
        grid_servo = QGridLayout()
        grid_servo.setHorizontalSpacing(10) # 열 사이 간격
        grid_servo.setVerticalSpacing(5)    # 행 사이 간격

        # 레이블 생성 및 초기화
        self.lbl_tool_revolution_rpm = self._create_label()
        self.lbl_tool_rotation_rpm = self._create_label()
        self.lbl_turntable_degree = self._create_label()
        self.lbl_turntable_rpm = self._create_label()

        # 그리드 배치
        servo_rows = [
            (0, "Tool Rev (Axis 1)", self.lbl_tool_revolution_rpm, "RPM"),
            (1, "Tool Rot (Axis 2)", self.lbl_tool_rotation_rpm, "RPM"),
            (2, "Turntable Pos (Axis 3)", self.lbl_turntable_degree, "deg"),
            (3, "Turntable Vel (Axis 3)", self.lbl_turntable_rpm, "RPM"),
        ]
        self._populate_grid(grid_servo, servo_rows)

        # 그룹박스 레이아웃에 서보 그리드 추가
        grid_layout.addLayout(grid_servo)

        # --- 레이아웃 설정 --- #
        grid_layout.addStretch() # 남는공간 채우기 (데이터가 위로 붙도록)
        group_box.setLayout(grid_layout)
        main_layout.addWidget(group_box)


    def _create_label(self) -> QLabel:
        """레이블 생성 및 초기화"""
        label = QLabel("0.000")
        label.setObjectName("wc_value")  # QSS ID
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _populate_grid(self, grid_layout: QGridLayout, rows: list):
        """그리드 배치"""
        for row_idx, name, val_lbl, unit_text in rows:
            # 1열: 축 이름
            name_lbl = QLabel(f"{name} :")
            name_lbl.setObjectName("wc_name") # QSS ID
            grid_layout.addWidget(name_lbl, row_idx, 0)
            
            # 2열: 값 (숫자)
            grid_layout.addWidget(val_lbl, row_idx, 1)
            
            # 3열: 단위
            unit_lbl = QLabel(unit_text)
            unit_lbl.setObjectName("wc_unit") # QSS ID
            grid_layout.addWidget(unit_lbl, row_idx, 2)

        grid_layout.setColumnStretch(1, 1)

    # ==========================================================
    # UI 업데이트 Slots
    # ==========================================================
    def update_data(self, data: FANUCPose):
        """
        data를 받아 UI 업데이트
            BaseWidget의 safe_update_data()를 통해 호출됨
        """
        if not hasattr(data, 'x'): return

        if self.lbl_x: self.lbl_x.setText(f"{data.x:.3f}")
        if self.lbl_y: self.lbl_y.setText(f"{data.y:.3f}")
        if self.lbl_z: self.lbl_z.setText(f"{data.z:.3f}")
        if self.lbl_w: self.lbl_w.setText(f"{data.w:.3f}")
        if self.lbl_p: self.lbl_p.setText(f"{data.p:.3f}")
        if self.lbl_r: self.lbl_r.setText(f"{data.r:.3f}")

    @pyqtSlot(ServoPose)
    def _update_tool_revolution_ui(self, pose: ServoPose):
        if self.lbl_tool_revolution_rpm: self.lbl_tool_revolution_rpm.setText(f"{pose.velocity:.1f}")

    @pyqtSlot(ServoPose)
    def _update_tool_rotation_ui(self, pose: ServoPose):
        if self.lbl_tool_rotation_rpm: self.lbl_tool_rotation_rpm.setText(f"{pose.velocity:.1f}")

    @pyqtSlot(ServoPose)
    def _update_turntable_ui(self, pose: ServoPose):
        if self.lbl_turntable_degree: self.lbl_turntable_degree.setText(f"{pose.angle:.2f}")
        if self.lbl_turntable_rpm: self.lbl_turntable_rpm.setText(f"{pose.velocity:.1f}")





"""
Smoke Test

python -m ui.widgets.world_coordinates_widget
"""
if __name__ == "__main__":
    import sys
    import random
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    from core.event_bus import EVENT_BUS
    from services.plc_service import PLCService
    from view_models.world_coordinates_viewmodel import WorldCoordinatesViewModel
    from models.servo_pose_key import ServoAxis
    from utils.dll_loader import load_pyads_dll

    try: load_pyads_dll()
    except: pass

    app = QApplication(sys.argv)
    
    service = PLCService()
    vm = WorldCoordinatesViewModel()
    window = WorldCoordinatesWidget()
    window.set_view_model(vm)
    window.resize(300, 450)
    window.show()

    service.connector._handle = 1

    def mock_robot():
        return FANUCPose(x=random.uniform(0, 100), y=10.5, z=50.0, w=0, p=0, r=0)

    def mock_servo():
        return {
            ServoAxis.TOOL_REVOLUTION: ServoPose(velocity=random.uniform(0, 60)),
            ServoAxis.TOOL_ROTATION: ServoPose(velocity=random.uniform(0, 120)),
            ServoAxis.TURNTABLE: ServoPose(angle=random.uniform(0, 360), velocity=10.0)
        }

    sim_timer = QTimer()
    sim_timer.setInterval(100)
    sim_timer.timeout.connect(lambda: EVENT_BUS.control.robot_current_pose.emit(mock_robot()))
    sim_timer.timeout.connect(lambda: EVENT_BUS.control.servo_current_motion.emit(mock_servo()))
    sim_timer.start()

    sys.exit(app.exec())

