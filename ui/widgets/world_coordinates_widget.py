# ui/widgets/world_coordinates_widget.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QGroupBox, QGridLayout, QLabel
from typing import TYPE_CHECKING, Optional
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
        if self.vm:
            self.vm.robot_pose_changed.connect(self.safe_update_data)


    def _init_ui(self):
        """UI 구성"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setObjectName("world_coordinates_widget")  # 전체 위젯 ID

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
            name_lbl = QLabel(f"{name} :")
            name_lbl.setObjectName("wc_name") # QSS ID
            grid_layout.addWidget(name_lbl, row_idx, 0)
            
            # 2열: 값 (숫자)
            grid_layout.addWidget(val_lbl, row_idx, 1)
            
            # 3열: 단위
            unit_lbl = QLabel(unit_text)
            unit_lbl.setObjectName("wc_unit") # QSS ID
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
    from core.event_bus import EVENT_BUS


    # [1] 설정 및 유틸리티
    from config.paths import STYLESHEET_PATH
    from styles.style_manager import load_and_apply_stylesheet
    from utils.dll_loader import load_pyads_dll

    # [중요] DLL 로드를 서비스 임포트보다 먼저 수행해야 함 (pyads 의존성 때문)
    try:
        load_pyads_dll()
        print("✅ DLL 로드 완료")
    except Exception as e:
        print(f"⚠️ DLL 로드 실패: {e}")

    # [2] MVVM 아키텍처 요소 임포트
    from core.event_bus import EVENT_BUS
    from models.fanuc_pose_model import FANUCPose
    from services.plc_service import PLCService
    from view_models.world_coordinates_viewmodel import WorldCoordinatesViewModel

    app = QApplication(sys.argv)

    # 스타일시트 적용
    try:
        load_and_apply_stylesheet(app, STYLESHEET_PATH)
        print("✅ 스타일시트 적용 완료")
    except Exception as e:
        print(f"⚠️ 스타일시트 로드 실패: {e}")

    # ----------------------------------------------------------------
    # [3] 아키텍처 조립 (Service -> VM -> View)
    # ----------------------------------------------------------------
    
    # 1. 서비스 생성
    service = PLCService()
    
    # 2. 뷰모델 생성 (내부적으로 EventBus를 구독함)
    vm = WorldCoordinatesViewModel()

    # 3. 뷰 생성 및 뷰모델 주입
    window = WorldCoordinatesWidget()
    window.set_view_model(vm)
    
    window.setWindowTitle("World Coordinates (Architecture Test)")
    window.resize(350, 250)
    window.show()

    # ----------------------------------------------------------------
    # [4] 데이터 시뮬레이션 (Mocking)
    # ----------------------------------------------------------------
    # 실제 PLC가 없으므로, 서비스가 데이터를 읽어오는 부분만
    # '랜덤 데이터 생성 함수'로 바꿔치기(Monkey Patch) 합니다.
    
    print("🛠️ 모의(Mock) 데이터 환경 구성 중...")

    # (A) 강제로 연결된 상태로 위장 (모니터링 루프가 돌기 위해)
    # TwinCATConnector의 내부 핸들을 가짜 값(1)으로 설정
    service.connector._handle = 1  # type: ignore

    # (B) 로봇 데이터를 읽어오는 메서드를 '랜덤 함수'로 교체
    def mock_read_pose():
        return FANUCPose(
            x=random.uniform(0, 500),
            y=random.uniform(-200, 200),
            z=random.uniform(100, 300),
            w=random.uniform(-180, 180),
            p=random.uniform(-90, 90),
            r=random.uniform(-180, 180)
        )
    
    # 메서드 덮어쓰기 (Hijacking)
    service.commander.robot.read_current_world_pose = mock_read_pose

    # ----------------------------------------------------------------
    # [5] 타이머 실행 (가상 데이터 직접 방송)
    # ----------------------------------------------------------------
    # PLCService를 거치지 않고, 타이머가 직접 mock 데이터를 생성하여
    # 전역 이벤트 버스로 방송합니다.
    
    sim_timer = QTimer()
    sim_timer.setInterval(100)  # 100ms
    
    # [핵심] 타이머마다 mock_read_pose()를 호출하고 그 결과를 직접 emit
    sim_timer.timeout.connect(lambda: EVENT_BUS.control.robot_current_pose.emit(mock_read_pose()))
    
    sim_timer.start()

    print("🚀 시뮬레이션 시작: 타이머가 직접 전역 시그널을 방송합니다.")

    sys.exit(app.exec())
