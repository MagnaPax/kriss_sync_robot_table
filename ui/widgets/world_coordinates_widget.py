# ui/widgets/world_coordinates_widget.py
from typing import TYPE_CHECKING, Optional
from PyQt6.QtWidgets import QVBoxLayout, QGroupBox, QFormLayout, QLabel
from core.event_bus import EVENT_BUS
from ui.widgets.base_widget import BaseWidget

if TYPE_CHECKING:
    from view_models.world_coordinates_viewmodel import WorldCoordinatesViewModel



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

        # ViewModel 인스턴스를 클래스 속성으로 저장
        # super().__init__() 전에 저장
        self.vm: Optional["WorldCoordinatesViewModel"] = None
        
        # BaseWidget의 __init__()이 _init_ui() 호출 → 실제 UI 생성
        super().__init__(parent)
        
        # 이벤트 연결 (UI만들어진 뒤)
        self._bind_events()


    def set_view_model(self, view_model: "WorldCoordinatesViewModel"):
        """외부에서 뷰모델을 꽂아주는 함수(Setter)"""
        self.vm = view_model


    def _bind_events(self):
        """EventBus 시그널 연결"""
        # PLCService._on_monitor_tick 에서 방송하는 로봇 현재 위치 수신
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






# ==========================================================
# Smoke Test
"""
실행 방법:
python -m ui.widgets.world_coordinates_widget
"""
# ==========================================================
if __name__ == "__main__":
    import sys
    import random
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer

    # [1] 설정 및 유틸리티 임포트
    from config.paths import STYLESHEET_PATH
    from styles.style_manager import load_and_apply_stylesheet
    
    # [2] 모델 및 이벤트 버스 임포트
    from models.fanuc_pose_model import FANUCPose
    from core.event_bus import EVENT_BUS

    # [3] DLL 로드 (사용자 요청)
    from utils.dll_loader import load_pyads_dll
    try:
        load_pyads_dll()
        print("✅ DLL 로드 완료")
    except Exception as e:
        print(f"⚠️ DLL 로드 실패: {e}")

    app = QApplication(sys.argv)

    # [4] 스타일시트 적용
    try:
        load_and_apply_stylesheet(app, STYLESHEET_PATH)
        print("✅ 스타일시트 적용 완료")
    except Exception as e:
        print(f"⚠️ 스타일시트 로드 실패: {e}")

    # [5] 위젯 생성 및 표시
    window = WorldCoordinatesWidget()
    window.setWindowTitle("World Coordinates (Smoke Test)")
    window.resize(300, 250)
    window.show()

    # [6] 데이터 시뮬레이션 (PLCService 역할 흉내내기)
    # 실제 로봇이 없어도 위젯이 작동하는지 확인하기 위해 
    # 0.1초마다 랜덤 좌표를 EventBus로 방송합니다.
    sim_timer = QTimer()
    sim_timer.setInterval(100)  # 100ms (10Hz)

    def simulate_robot_data():
        # 테스트용 랜덤 좌표 생성
        fake_pose = FANUCPose(
            x=random.uniform(0, 500),
            y=random.uniform(-200, 200),
            z=random.uniform(100, 300),
            w=random.uniform(-180, 180),
            p=random.uniform(-90, 90),
            r=random.uniform(-180, 180)
        )
        
        # EventBus로 발송 -> 위젯이 update_data로 수신
        EVENT_BUS.control.robot_current_pose.emit(fake_pose)

    sim_timer.timeout.connect(simulate_robot_data)
    sim_timer.start()

    print("🚀 시뮬레이션 시작: 랜덤 좌표 데이터 전송 중...")

    sys.exit(app.exec())
