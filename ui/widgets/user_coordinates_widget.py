# ui/widgets/user_coordinates.py
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QGroupBox, QPushButton, QWidget
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
    # ========================================
    # 초기화 및 설정 (Initialization)
    # ========================================
    def __init__(self, parent: Optional[QWidget] = None):
        # ViewModel 타입 힌트 재정의를 위해 초기화
        self.btn_robot_origin = None
        self.btn_servo_origin = None
        self.btn_reset = None
        self.viewmodel: Optional["UserCoordinatesViewModel"] = None
        super().__init__(parent)

    def set_view_model(self, view_model: "UserCoordinatesViewModel"): # type: ignore[override]
        """ViewModel 주입 및 이벤트 연결 (Override)"""
        self.viewmodel = view_model
        self._bind_events()

    def _bind_events(self):
        """UserCoordinatesViewModel의 시그널 연결 (Override)"""
        if not self.viewmodel: return
        
        if btn := self.btn_robot_origin: btn.clicked.connect(self._on_robot_origin_clicked)
        if btn := self.btn_servo_origin: btn.clicked.connect(self._on_servo_origin_clicked)
        if btn := self.btn_reset: btn.clicked.connect(self._on_origin_all_clicked)


    # ========================================
    # UI 구성 (Initialization)
    # ========================================
    def _init_ui(self):
        """UI 초기화 (부모 클래스 로직 재사용 + 커스터마이징)"""
        # 1. WorldCoordinatesWidget의 UI 구성 로직 실행
        super()._init_ui()
        
        self.setObjectName("user_coordinates_widget")   # QSS ID

        layout = self.layout()

        if layout and layout.count() > 0:
            item = layout.itemAt(0)
            if item and (widget := item.widget()) and isinstance(widget, QGroupBox):
                widget.setTitle("User Coordinates")

                # 버튼 추가
                if gb_layout := widget.layout():
                    # 버튼 생성
                    self.btn_robot_origin = QPushButton("Set Robot Origin")
                    self.btn_servo_origin = QPushButton("Set Servo Origin")
                    self.btn_reset = QPushButton("Set Origin All")

                    # 스타일 적용
                    self.btn_robot_origin.setProperty("type", "general")
                    self.btn_servo_origin.setProperty("type", "general")
                    self.btn_reset.setProperty("type", "special")

                    # 레이아웃에 추가 (WorldCoordinatesWidget의 addStretch() 뒤에 추가됨 -> 하단 배치)
                    gb_layout.addWidget(self.btn_robot_origin)
                    gb_layout.addWidget(self.btn_servo_origin)
                    gb_layout.addWidget(self.btn_reset)


    # ===============================================
    # 데이터 처리
    # ===============================================
    def clear_widget(self):
        """위젯 상태 초기화"""
        # 라벨 텍스트 초기화
        if self.lbl_x: self.lbl_x.setText("0.000")
        if self.lbl_y: self.lbl_y.setText("0.000")
        if self.lbl_z: self.lbl_z.setText("0.000")
        if self.lbl_w: self.lbl_w.setText("0.000")
        if self.lbl_p: self.lbl_p.setText("0.000")
        if self.lbl_r: self.lbl_r.setText("0.000")

        if self.lbl_tool_revolution_rpm: self.lbl_tool_revolution_rpm.setText("0.000")
        if self.lbl_tool_rotation_rpm: self.lbl_tool_rotation_rpm.setText("0.000")
        if self.lbl_turntable_degree: self.lbl_turntable_degree.setText("0.000")
        if self.lbl_turntable_rpm: self.lbl_turntable_rpm.setText("0.000")

        # 부모 클래스의 초기화(데이터 비우기) 호출
        super().clear_widget()


    # ===============================================
    # 이벤트 슬롯 [물리적 신호 처리]
    #   - 사용자 입력(클릭, 선택)에 대한 신호 처리
    # ===============================================
    @pyqtSlot()
    def _on_robot_origin_clicked(self):
        """"""
        self._handle_robot_origin()

    @pyqtSlot()
    def _on_servo_origin_clicked(self):
        """"""
        self._handle_servo_origin()

    @pyqtSlot()
    def _on_origin_all_clicked(self):
        """"""
        self._handle_origin_all()



    # ===============================================
    # 핸들러 [논리적 흐름 담당]
    #   - 입력 데이터 가공 및 뷰모델 통신
    # ===============================================
    def _handle_robot_origin(self):
        if self.viewmodel:
            self.viewmodel.origin_robot_pose()

    def _handle_servo_origin(self):
        if self.viewmodel:
            self.viewmodel.origin_servo_pose()

    def _handle_origin_all(self):
        if self.viewmodel:
            self.viewmodel.origin_all_pose()











"""
Smoke Test

python -m ui.widgets.user_coordinates_widget
"""
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    try:
        # [순서 중요] DLL 로더를 가장 먼저 임포트하고 실행해야 함
        # PLCService -> ... -> pyads 임포트 시점에 DLL이 필요하기 때문
        from utils.dll_loader import load_pyads_dll
        try:
            load_pyads_dll()
        except Exception:
            pass

        from services.plc_service import PLCService
        from view_models.user_coordinates_viewmodel import UserCoordinatesViewModel
        from config.paths import STYLESHEET_PATH
        from styles.style_manager import load_and_apply_stylesheet
    except ImportError as e:
        print(f"Import Error: {e}")
        print("프로젝트 루트에서 'python -m ui.widgets.user_coordinates_widget' 명령어로 실행해주세요.")
        sys.exit(1)

    app = QApplication(sys.argv)

    # 스타일 적용
    load_and_apply_stylesheet(app, STYLESHEET_PATH)

    # 위젯 생성 및 설정
    service = PLCService()
    vm = UserCoordinatesViewModel(service)
    
    window = UserCoordinatesWidget()
    window.set_view_model(vm)
    window.resize(350, 500)
    window.show()

    sys.exit(app.exec())
