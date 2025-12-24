# ui/widgets/servo_control_widget.py
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout, 
    QGroupBox, 
    QLabel, 
    QFrame, 
    QHBoxLayout, 
    QFormLayout, 
    QDoubleSpinBox, 
    QPushButton
)
from ui.widgets.base_widget import BaseWidget
from typing import TYPE_CHECKING, Any, Optional
from core.event_bus import EVENT_BUS

if TYPE_CHECKING:
    from view_models.servo_control_viewmodel import ServoControlViewModel



class ServoControlWidget(BaseWidget):
    """서보모터 제어용 위젯"""
    # ========================================
    # 초기화 및 설정 (Initialization)
    # ========================================
    def __init__(self, parent=None):
        """위젯 초기화"""
        # ViewModel 인스턴스를 클래스 속성으로 저장
        self.vm: Optional["ServoControlViewModel"] = None
        
        # 입력 위젯 보관함
        self.input_widgets: dict[str, QDoubleSpinBox] = {}
        
        # 버튼 참조
        self.btn_start = None
        self.btn_stop = None
        self.btn_home = None

        # BaseWidget의 __init__()은 내부적으로 _init_ui()를 호출함
        super().__init__(parent)
        
        # 이벤트 바인딩 (UI 생성 후)
        self._bind_events()

    def set_view_model(self, view_model: "ServoControlViewModel"):
        """
        외부에서 뷰모델을 주입하는 함수
        """
        self.vm = view_model

    def _bind_events(self):
        """UI 이벤트 바인딩"""
        if btn := self.btn_start: btn.clicked.connect(self._on_start_clicked)
        if btn := self.btn_stop:  btn.clicked.connect(self._on_stop_clicked)
        if btn := self.btn_home:  btn.clicked.connect(self._on_home_clicked)



    # ========================================
    # UI 구성 (Initialization)
    # ========================================
    def _init_ui(self):
        """UI 구성 (BaseWidget._init_ui 오버라이드)"""
        # 메인 레이아웃 및 그룹박스 설정
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setObjectName("servo_control_widget")

        # 그룹박스 생성
        self.servo_group = QGroupBox("Servo Control")
        group_layout = QVBoxLayout(self.servo_group)
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(15, 15, 15, 15)

        # 1. 입력 필드 영역 (공전, 자전, 턴테이블)
        input_section = QFrame()
        input_layout = QHBoxLayout(input_section)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(20)

        # 왼쪽: 공전/자전 (RPM)
        tool_layout = QFormLayout()
        self.input_widgets["rev_rpm"] = self._create_spinbox(0, 3000, 10)
        self.input_widgets["rot_rpm"] = self._create_spinbox(0, 3000, 10)
        tool_layout.addRow("공전 (rpm):", self.input_widgets["rev_rpm"])
        tool_layout.addRow("자전 (rpm):", self.input_widgets["rot_rpm"])

        # 오른쪽: 턴테이블 (각도/RPM)
        tt_layout = QFormLayout()
        self.input_widgets["tt_angle"] = self._create_spinbox(-360, 360, 0)
        self.input_widgets["tt_rpm"] = self._create_spinbox(0, 100, 5)
        tt_layout.addRow("턴테이블 각도 (deg):", self.input_widgets["tt_angle"])
        tt_layout.addRow("턴테이블 속도 (rpm):", self.input_widgets["tt_rpm"])

        input_layout.addLayout(tool_layout)
        input_layout.addLayout(tt_layout)

        # 2. 제어 버튼 영역 (START, STOP, HOME)
        button_section = QFrame()
        button_layout = QHBoxLayout(button_section)
        button_layout.setContentsMargins(0, 5, 0, 0)
        button_layout.setSpacing(10)

        self.btn_start = self._create_control_button("START", "special")
        self.btn_stop = self._create_control_button("STOP", "general")
        self.btn_home = self._create_control_button("HOME", "special")

        button_layout.addStretch(1)
        button_layout.addWidget(self.btn_start)
        button_layout.addWidget(self.btn_stop)
        button_layout.addWidget(self.btn_home)

        # 그룹 레이아웃에 섹션 추가
        group_layout.addWidget(input_section)
        group_layout.addWidget(button_section)
        
        main_layout.addWidget(self.servo_group)

    def _create_spinbox(self, min_val, max_val, default_val, suffix="") -> QDoubleSpinBox:
        """스핀박스 생성 헬퍼"""
        spin = QDoubleSpinBox()
        spin.setRange(float(min_val), float(max_val))
        spin.setValue(float(default_val))
        spin.setSuffix(suffix)
        spin.setDecimals(1)
        spin.setSingleStep(1.0)
        spin.setFixedWidth(100)
        # TargetPositionWidget 스타일 참고: 포커스 시 전체 선택
        spin.focusInEvent = lambda e: QTimer.singleShot(0, spin.selectAll)
        return spin

    def _create_control_button(self, text, btn_type) -> QPushButton:
        """제어 버튼 생성 헬퍼"""
        btn = QPushButton(text)
        btn.setFixedSize(80, 30)
        btn.setProperty("type", btn_type)
        return btn



    # ===============================================
    # 데이터 처리
    # ===============================================
    def update_data(self, data: Any):
        """
        데이터(dict)를 받아 UI 업데이트
            BaseWidget의 safe_update_data()를 통해 호출됨
        """
        # 상태에 따른 활성화/비활성화
        # TODO: 서보 모터가 물리적으로 움직이는 중이면 모든 버튼 비활성화
        pass

    def clear_widget(self):
        """위젯 상태 초기화"""
        # 입력창 값을 0으로 초기화
        for spin in self.input_widgets.values():
            spin.setValue(0.0)

        # 버튼 활성화 복구
        # 존재 여부를 확인(Safety Check)함과 동시에 setEnabled를 호출
        if btn := self.btn_start: btn.setEnabled(True)
        if btn := self.btn_stop:  btn.setEnabled(False)
        if btn := self.btn_home:  btn.setEnabled(True)

        # 부모 클래스의 초기화(데이터 비우기) 호출
        super().clear_widget()

    def _get_input_data(self) -> dict[str, float]:
        """입력 필드에서 데이터를 추출"""
        return {key: spin.value() for key, spin in self.input_widgets.items()}



    # ===============================================
    # 이벤트 슬롯 [물리적 신호 처리]
    #   - 사용자 입력(클릭, 선택)에 대한 신호 처리
    # =============================================== 
    @pyqtSlot()
    def _on_start_clicked(self):
        """START 버튼 클릭 핸들러"""
        self._handle_manual_start()

    @pyqtSlot()
    def _on_stop_clicked(self):
        """STOP 버튼 클릭 핸들러"""
        self._handle_manual_stop()

    @pyqtSlot()
    def _on_home_clicked(self):
        """HOME 버튼 클릭 핸들러"""
        self._handle_manual_home()



    # ===============================================
    # 핸들러 [논리적 흐름 담당]
    #   - 입력 데이터 가공 및 뷰모델 통신
    # ===============================================
    def _handle_manual_start(self):
        """MANUAL START 핸들러"""
        if not (vm := self.vm): return
        data = self._get_input_data()
        EVENT_BUS.log.message.emit(f"{self.log_prefix} MANUAL START: {data}", "DEBUG")
        vm.start_manual(data)

    def _handle_manual_stop(self):
        """MANUAL STOP 핸들러"""
        if not (vm := self.vm): return
        EVENT_BUS.log.message.emit(f"{self.log_prefix} MANUAL STOP", "DEBUG")
        vm.stop_manual()

    def _handle_manual_home(self):
        """MANUAL HOME 핸들러"""
        if not (vm := self.vm): return
        EVENT_BUS.log.message.emit(f"{self.log_prefix} MANUAL HOME", "DEBUG")
        vm.home_manual()



# ==========================================================
# Smoke Test
# ==========================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    from config.paths import STYLESHEET_PATH
    from styles.style_manager import load_and_apply_stylesheet

    from utils.dll_loader import load_pyads_dll
    try:
        load_pyads_dll()
        print("✅ DLL 로드 완료")
    except Exception as e:
        print(f"⚠️ DLL 로드 실패: {e}")


    from view_models.servo_control_viewmodel import ServoControlViewModel
    from communication.servo_adapter import ServoAdapter
    from communication.twincat_connector import TwinCATConnector

    # TwinCAT 연결 객체 생성
    connector = TwinCATConnector()
    # 데모 모드로 실행될 것이므로 별도의 connect() 호출 없이도 어댑터 초기화 가능
    
    servo_adapter = ServoAdapter(connector)
    vm = ServoControlViewModel(servo_adapter)


    app = QApplication(sys.argv)
    
    # 스타일 적용
    try:
        load_and_apply_stylesheet(app, STYLESHEET_PATH)
    except Exception as e:
        print(f"스타일 로드 실패: {e}")

    # 위젯 생성 및 테스트
    window = ServoControlWidget()
    window.set_view_model(vm)
    window.resize(400, 200)
    window.show()

    sys.exit(app.exec())


