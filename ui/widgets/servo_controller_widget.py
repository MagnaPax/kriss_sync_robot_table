# ui/widgets/servo_controller_widget.py
from PyQt6.QtCore import QTimer, pyqtSlot
from PyQt6.QtWidgets import (
    QVBoxLayout, 
    QGroupBox, 
    QFrame, 
    QHBoxLayout, 
    QFormLayout, 
    QDoubleSpinBox, 
    QPushButton,
    QWidget
)
from config.data_formats import (
    KEY_TURNTABLE_DEG,
    KEY_TURNTABLE_FEED_RATE,
    KEY_TOOL_REV_RPM,
    KEY_TOOL_ROT_RPM
)
from ui.widgets.base_widget import BaseWidget
from typing import TYPE_CHECKING, Any, Optional
from core.event_bus import EVENT_BUS
from core.settings import SETTINGS

if TYPE_CHECKING:
    from view_models.servo_control_viewmodel import ServoControlViewModel



class ServoControllerWidget(BaseWidget):
    """서보모터 제어용 위젯"""
    # ========================================
    # 초기화 및 설정 (Initialization)
    # ========================================
    def __init__(self, parent: Optional[QWidget] = None):
        """위젯 초기화"""
        # ViewModel 인스턴스를 클래스 속성으로 저장
        self.vm: Optional["ServoControlViewModel"] = None
        
        # 입력 위젯 보관함
        self.input_widgets: dict[str, QDoubleSpinBox] = {}
        
        # 버튼 참조
        self.btn_start = None
        self.btn_tt_start = None
        self.btn_stop = None
        self.btn_home = None
        self.btn_reset = None

        # BaseWidget의 __init__()은 내부적으로 _init_ui()를 호출함
        super().__init__(parent)
        
        # 이벤트 바인딩 (UI 생성 후)
        self._bind_events()

    def set_view_model(self, view_model: "ServoControlViewModel"):
        """외부에서 뷰모델을 주입하는 함수"""
        self.vm = view_model

        # 로봇과 턴테이블의 바쁨 상태 연결
        self.vm.busy_state_changed.connect(self.safe_update_data)
        self.vm.servo_inputs_clear.connect(self.clear_widget)
        self.vm.servo_axis_motion_changed.connect(self.safe_update_data)

    def _bind_events(self):
        """UI 이벤트 바인딩"""
        if btn := self.btn_start: btn.clicked.connect(self._on_start_clicked)
        if btn := self.btn_tt_start: btn.clicked.connect(self._on_tt_start_clicked)
        if btn := self.btn_stop:  btn.clicked.connect(self._on_stop_clicked)
        if btn := self.btn_home:  btn.clicked.connect(self._on_home_clicked)
        if btn := self.btn_reset: btn.clicked.connect(self._on_reset_clicked)



    # ========================================
    # UI 구성 (Initialization)
    # ========================================
    def _init_ui(self):
        """UI 구성 (BaseWidget._init_ui 오버라이드)"""
        # 메인 레이아웃 및 그룹박스 설정
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setObjectName("servo_controller_widget")

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
        self.input_widgets[KEY_TOOL_REV_RPM] = self._create_spinbox(
            SETTINGS.servo.tool_rpm_min, SETTINGS.servo.tool_rpm_max, SETTINGS.servo.tool_rpm_default
        )
        self.input_widgets[KEY_TOOL_ROT_RPM] = self._create_spinbox(
            SETTINGS.servo.tool_rpm_min, SETTINGS.servo.tool_rpm_max, SETTINGS.servo.tool_rpm_default
        )
        tool_layout.addRow("공전 (rpm):", self.input_widgets[KEY_TOOL_REV_RPM])
        tool_layout.addRow("자전 (rpm):", self.input_widgets[KEY_TOOL_ROT_RPM])

        # 오른쪽: 턴테이블 (각도/RPM)
        tt_layout = QFormLayout()
        self.input_widgets[KEY_TURNTABLE_DEG] = self._create_spinbox(
            SETTINGS.servo.turntable_deg_min, SETTINGS.servo.turntable_deg_max, SETTINGS.servo.turntable_deg_default
        )
        self.input_widgets[KEY_TURNTABLE_FEED_RATE] = self._create_spinbox(
            SETTINGS.servo.turntable_rpm_min, SETTINGS.servo.turntable_rpm_max, SETTINGS.servo.turntable_rpm_default
        )
        tt_layout.addRow("턴테이블 각도 (deg):", self.input_widgets[KEY_TURNTABLE_DEG])
        tt_layout.addRow("턴테이블 속도 (rpm):", self.input_widgets[KEY_TURNTABLE_FEED_RATE])

        input_layout.addLayout(tool_layout)
        input_layout.addLayout(tt_layout)

        # 2. 제어 버튼 영역 (START, STOP, HOME)
        button_section = QFrame()
        button_layout = QHBoxLayout(button_section)
        button_layout.setContentsMargins(0, 5, 0, 0)
        button_layout.setSpacing(10)

        self.btn_start = self._create_control_button("START", "special")
        self.btn_tt_start = self._create_control_button("TT ONLY", "special")
        self.btn_stop = self._create_control_button("STOP", "general")
        self.btn_home = self._create_control_button("HOME", "special")
        self.btn_reset = self._create_control_button("RESET", "general")

        button_layout.addStretch(1)
        button_layout.addWidget(self.btn_start)
        button_layout.addWidget(self.btn_tt_start)
        button_layout.addWidget(self.btn_stop)
        button_layout.addWidget(self.btn_home)
        button_layout.addWidget(self.btn_reset)

        # 그룹 레이아웃에 섹션 추가
        group_layout.addWidget(input_section)
        group_layout.addWidget(button_section)
        
        main_layout.addWidget(self.servo_group)

    def _create_spinbox(self, min_val: float, max_val: float, default_val: float, suffix: str = "") -> QDoubleSpinBox:
        """스핀박스 생성 헬퍼"""
        spin = QDoubleSpinBox()
        spin.setRange(float(min_val), float(max_val))
        spin.setValue(float(default_val))
        spin.setSuffix(suffix)
        spin.setDecimals(1)
        spin.setSingleStep(1.0)
        spin.setFixedWidth(100)

        # 음수 입력 차단 로직 (최소값이 0 이상일 때)
        if min_val >= 0:
            def validate_no_minus(text: str):
                if '-' in text:
                    # 1. 시그널 방출 (메인 윈도우에서 팝업)
                    EVENT_BUS.system.operation_error_alert.emit(
                        "입력 불가", 
                        "속도 항목에는 음수(-)를 입력할 수 없습니다."
                    )
                    # 2. '-' 문자 강제 삭제
                    line_edit = spin.lineEdit()
                    line_edit.blockSignals(True)
                    line_edit.setText(text.replace('-', ''))
                    line_edit.blockSignals(False)
            
            spin.lineEdit().textChanged.connect(validate_no_minus)

        # RobotControllerWidget 스타일 참고: 포커스 시 전체 선택
        spin.focusInEvent = lambda e: QTimer.singleShot(0, spin.selectAll)
        return spin

    def _create_control_button(self, text: str, btn_type: str) -> QPushButton:
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
        [Override] BaseWidget.update_data
        실제 UI 업데이트 로직 (safe_update_data에 의해 호출됨)
        """
        if not isinstance(data, dict): return
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 화면 업데이트 할 데이터: {data}", "DEBUG")

        # --- case 1 --- #
        # 상태 업데이트 (is_servo_moving)
        if 'is_servo_moving' in data:
            is_busy = data['is_servo_moving']

            # BaseWidget 내부 변수 업데이트
            self._is_enabled = not is_busy

            # 로봇/서보가 바쁘면 START, HOME, RESET 비활성화, STOP 활성화
            if self.btn_start: self.btn_start.setEnabled(not is_busy)
            if self.btn_tt_start: self.btn_tt_start.setEnabled(not is_busy)
            if self.btn_home:  self.btn_home.setEnabled(not is_busy)
            if self.btn_reset: self.btn_reset.setEnabled(not is_busy)
            if self.btn_stop:  self.btn_stop.setEnabled(is_busy)
            
            # 입력창들도 비활성화하여 오작동 방지
            for spin in self.input_widgets.values():
                spin.setEnabled(not is_busy)

        # --- case 2 --- #
        # 서보 값 업데이트 (PLC 또는 테이블 선택으로부터 온 데이터)
        target_keys = [
            KEY_TURNTABLE_DEG, 
            KEY_TURNTABLE_FEED_RATE, 
            KEY_TOOL_REV_RPM, 
            KEY_TOOL_ROT_RPM
        ]

        for key in target_keys:
            # 데이터 딕셔너리에 키가 존재하는지 확인 (None이 아니면 0이어도 진행)
            if (val := data.get(key)) is not None:
                # 해당 값을 표시할 UI 위젯(SpinBox)이 등록되어 있는지 확인
                if widget := self.input_widgets.get(key):
                    # 값이 바뀌었다는 시그널 잠시 차단 - 안 하면 무한 루프 발생
                    blocker = widget.blockSignals(True)
                    widget.setValue(float(val))         # 실제 위젯에 값 적용 (0.0 포함)
                    widget.blockSignals(blocker)        # 업데이트 후 차단 해제

    def clear_widget(self):
        """위젯 상태 초기화"""
        # 입력창 값을 0으로 초기화
        for spin in self.input_widgets.values():
            spin.setValue(0.0)

        # 버튼 활성화 복구
        # 존재 여부를 확인(Safety Check)함과 동시에 setEnabled를 호출
        if btn := self.btn_start: btn.setEnabled(True)
        if btn := self.btn_tt_start: btn.setEnabled(True)
        if btn := self.btn_stop:  btn.setEnabled(False)
        if btn := self.btn_home:  btn.setEnabled(True)
        if btn := self.btn_reset: btn.setEnabled(True)

        # 부모 클래스의 초기화(데이터 비우기) 호출
        super().clear_widget()

    def _get_input_data(self) -> dict[str, float]:
        """
        입력 필드(QDoubleSpinBox)에서 데이터를 추출하여
        '시스템 표준 키 상수'로 매핑된 딕셔너리를 반환
        """
        return {
            KEY_TOOL_REV_RPM: self.input_widgets[KEY_TOOL_REV_RPM].value(),
            KEY_TOOL_ROT_RPM: self.input_widgets[KEY_TOOL_ROT_RPM].value(),
            KEY_TURNTABLE_DEG: self.input_widgets[KEY_TURNTABLE_DEG].value(),
            KEY_TURNTABLE_FEED_RATE: self.input_widgets[KEY_TURNTABLE_FEED_RATE].value()
        }



    # ===============================================
    # 이벤트 슬롯 [물리적 신호 처리]
    #   - 사용자 입력(클릭, 선택)에 대한 신호 처리
    # =============================================== 
    @pyqtSlot()
    def _on_start_clicked(self):
        """START 버튼 클릭 핸들러"""
        self._handle_manual_start()

    @pyqtSlot()
    def _on_tt_start_clicked(self): # [추가]
        """TT ONLY START 버튼 클릭 핸들러"""
        self._handle_manual_tt_start()

    @pyqtSlot()
    def _on_stop_clicked(self):
        """STOP 버튼 클릭 핸들러"""
        self._handle_manual_stop()

    @pyqtSlot()
    def _on_home_clicked(self):
        """HOME 버튼 클릭 핸들러"""
        self._handle_manual_home()

    @pyqtSlot()
    def _on_reset_clicked(self):
        """RESET 버튼 클릭 핸들러"""
        self._handle_manual_reset()



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

    def _handle_manual_tt_start(self):
        """턴테이블 전용 START 핸들러 (스핀들 제외)"""
        if not (vm := self.vm): return
        
        # 전체 데이터에서 턴테이블 관련 키만 추출
        all_data = self._get_input_data()
        tt_data = {
            KEY_TURNTABLE_DEG: all_data[KEY_TURNTABLE_DEG],
            KEY_TURNTABLE_FEED_RATE: all_data[KEY_TURNTABLE_FEED_RATE]
        }
        
        EVENT_BUS.log.message.emit(f"{self.log_prefix} MANUAL TT START: {tt_data}", "DEBUG")
        # 뷰모델의 일반 시작 메서드 재사용 (데이터가 필터링됨)
        vm.start_manual(tt_data)

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

    def _handle_manual_reset(self):
        """MANUAL RESET 핸들러"""
        if not (vm := self.vm): return
        EVENT_BUS.log.message.emit(f"{self.log_prefix} MANUAL RESET", "DEBUG")
        vm.reset_manual()



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
    vm = ServoControlViewModel(servo_adapter) # type: ignore


    app = QApplication(sys.argv)
    
    # 스타일 적용
    try:
        load_and_apply_stylesheet(app, STYLESHEET_PATH)
    except Exception as e:
        print(f"스타일 로드 실패: {e}")

    # 위젯 생성 및 테스트
    window = ServoControllerWidget()
    window.set_view_model(vm)
    window.resize(400, 200)
    window.show()

    sys.exit(app.exec())
