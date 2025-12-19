# ui/widgets/world_coordinates_widget.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QGroupBox, QGridLayout, QLabel
from typing import TYPE_CHECKING, Optional
from ui.widgets.base_widget import BaseWidget
from core.event_bus import EVENT_BUS

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
        self.setObjectName("world_coordinates_widget")  # 스타일시트 적용 위한 QSS ID 부여

        # 그룹박스
        group_box = QGroupBox("FANUC World Coordinates")

        # 3열 구조(이름 | 값 | 단위)를 위해 QGridLayout 사용
        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(10) # 열 사이 간격
        grid_layout.setVerticalSpacing(5)    # 행 사이 간격
        
        # 레이블 생성 및 초기화
        self.lbl_x = QLabel("0.000")
        self.lbl_y = QLabel("0.000")
        self.lbl_z = QLabel("0.000")
        self.lbl_w = QLabel("0.000")
        self.lbl_p = QLabel("0.000")
        self.lbl_r = QLabel("0.000")

        # 값 레이블 스타일 및 정렬 (우측 정렬해야 숫자 자리수가 맞아 보임)
        for lbl in [self.lbl_x, self.lbl_y, self.lbl_z, self.lbl_w, self.lbl_p, self.lbl_r]:
            lbl.setObjectName("wc_value")  # QSS ID
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # 배치 (이름 | 값 | 단위)
        # 데이터 순서: 행 번호, 이름, 값 위젯, 단위 텍스트
        rows = [
            (0, "X", self.lbl_x, "mm"),
            (1, "Y", self.lbl_y, "mm"),
            (2, "Z", self.lbl_z, "mm"),
            (3, "W", self.lbl_w, "deg"),
            (4, "P", self.lbl_p, "deg"),
            (5, "R", self.lbl_r, "deg"),
        ]

        for row_idx, name, val_lbl, unit_text in rows:
            # 1열: 축 이름
            grid_layout.addWidget(QLabel(f"{name} :"), row_idx, 0)
            
            # 2열: 값 (숫자)
            grid_layout.addWidget(val_lbl, row_idx, 1)
            
            # 3열: 단위
            unit_lbl = QLabel(unit_text)
            unit_lbl.setStyleSheet("color: gray; font-size: 11px;") # 단위는 조금 작고 연하게
            grid_layout.addWidget(unit_lbl, row_idx, 2)

        # 2열(숫자 부분)이 남는 공간을 차지하도록 설정
        grid_layout.setColumnStretch(1, 1)

        group_box.setLayout(grid_layout)
        main_layout.addWidget(group_box)


    def update_data(self, data):
        """
        data를 받아 UI 업데이트
            BaseWidget의 safe_update_data()를 통해 호출됨
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
