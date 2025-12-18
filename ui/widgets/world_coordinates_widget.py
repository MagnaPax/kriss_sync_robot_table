# ui/widgets/world_coordinates_widget.py
from PyQt6.QtWidgets import QVBoxLayout, QGroupBox, QFormLayout, QLabel
from ui.widgets.base_widget import BaseWidget
from core.event_bus import EVENT_BUS

class WorldCoordinatesWidget(BaseWidget):
    """
    로봇의 현재 World 좌표(FANUCPose)를 실시간으로 모니터링하는 위젯
    """
    
    def __init__(self, parent=None):
        # UI 요소 변수 선언
        self.lbl_x = None
        self.lbl_y = None
        self.lbl_z = None
        self.lbl_w = None
        self.lbl_p = None
        self.lbl_r = None
        
        super().__init__(parent)
        
        # 이벤트 연결
        self._bind_events()

    def _bind_events(self):
        """EventBus 시그널 연결"""
        # PLCService._monitoring_loop에서 방송하는 로봇 현재 위치 수신
        EVENT_BUS.control.robot_current_pose.connect(self.safe_update_data)

    def _init_ui(self):
        """UI 구성"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 그룹박스
        group_box = QGroupBox("Robot World Pose (Feedback)")
        form_layout = QFormLayout()
        
        # 라벨 생성 및 초기화
        self.lbl_x = QLabel("0.000")
        self.lbl_y = QLabel("0.000")
        self.lbl_z = QLabel("0.000")
        self.lbl_w = QLabel("0.000")
        self.lbl_p = QLabel("0.000")
        self.lbl_r = QLabel("0.000")

        # 폼 레이아웃에 추가 (라벨 - 값)
        # 스타일: 숫자는 굵게 표시
        for lbl in [self.lbl_x, self.lbl_y, self.lbl_z, self.lbl_w, self.lbl_p, self.lbl_r]:
            lbl.setStyleSheet("font-weight: bold; color: #333;")

        form_layout.addRow("X (mm):", self.lbl_x)
        form_layout.addRow("Y (mm):", self.lbl_y)
        form_layout.addRow("Z (mm):", self.lbl_z)
        form_layout.addRow("W (deg):", self.lbl_w)
        form_layout.addRow("P (deg):", self.lbl_p)
        form_layout.addRow("R (deg):", self.lbl_r)

        group_box.setLayout(form_layout)
        main_layout.addWidget(group_box)

    def update_data(self, data):
        """
        데이터 업데이트 (FANUCPose 객체 수신)
        """
        # data는 FANUCPose 객체여야 함 (속성: x, y, z, w, p, r)
        if hasattr(data, 'x'):
            if self.lbl_x: self.lbl_x.setText(f"{data.x:.3f}")
            if self.lbl_y: self.lbl_y.setText(f"{data.y:.3f}")
            if self.lbl_z: self.lbl_z.setText(f"{data.z:.3f}")
            if self.lbl_w: self.lbl_w.setText(f"{data.w:.3f}")
            if self.lbl_p: self.lbl_p.setText(f"{data.p:.3f}")
            if self.lbl_r: self.lbl_r.setText(f"{data.r:.3f}")
