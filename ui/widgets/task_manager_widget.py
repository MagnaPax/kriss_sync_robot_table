# ui/widgets/task_manager_widget.py
from pathlib import Path
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import (
    QVBoxLayout, 
    QGroupBox, 
    QLabel, 
    QHBoxLayout, 
    QPushButton,
    QFileDialog,
    QWidget
)
from ui.widgets.base_widget import BaseWidget
from core.event_bus import EVENT_BUS
from typing import TYPE_CHECKING, Optional, Dict, Any


if TYPE_CHECKING:
    from view_models.task_manager_viewmodel import TaskManagerViewModel




class TaskManagerWidget(BaseWidget):
    """Sequence 파일 불러오기"""
    # ========================================
    # 초기화 및 설정 (Initialization)
    # ========================================
    def __init__(self, parent: Optional[QWidget] = None):
        """Sequence 파일 로드 및 실행 제어 위젯"""

        # UI 요소 참조 변수 초기화
        self.lbl_runtime_val = None
        self.btn_load = None
        self.lbl_filename = None
        self.btn_start = None
        self.btn_stop = None

        # ViewModel 인스턴스를 클래스 속성으로 저장
        # super().__init__() 전에 저장
        self.vm: Optional["TaskManagerViewModel"] = None

        # BaseWidget의 __init__()이 _init_ui() 호출 → 실제 UI 생성
        super().__init__(parent)

        # 이벤트 연결 (UI만들어진 뒤)
        self._bind_events()

        # 내부 상태 플래그
        self._is_sequence_running = False
        self._is_servo_busy = False

    def set_view_model(self, view_model: "TaskManagerViewModel"):
        """
        외부에서 뷰모델을 꽂아주는 함수(Setter)
            MainViewModel 이 TaskManagerViewModel 소유
            RightPanel 에서 TaskManagerWidget 에게 주입
        """
        self.vm = view_model

        # 로봇과 턴테이블의 바쁨 상태 연결
        self.vm.busy_state_changed.connect(self.update_data)
        
        # 시퀀스가 실행되고 있는지 아닌지 상태 변경 연결
        self.vm.sequence_running_changed.connect(self._update_running_state)

        # 런타임 시간 업데이트 연결
        # 뷰모델이 "00:00:01" 보내면 -> 라벨 setText 실행
        if (lbl := self.lbl_runtime_val) is not None:
            self.vm.runtime_updated.connect(lbl.setText)


    def _init_ui(self):

        # 메인 레이아웃 및 그룹박스 설정
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setObjectName("task_manager_widget")   # 전체 위젯 ID

        # 그룹박스 생성
        base_group_box = QGroupBox("Task Manager")
        # 그룹박스 내부 레이아웃 (세로 정렬)
        group_layout = QVBoxLayout(base_group_box)
        group_layout.setSpacing(10)                 # 각 구역 사이의 간격
        group_layout.setContentsMargins(15, 10, 15, 15)


        # --- 정보 표시 --- #
        info_layout = QHBoxLayout()
        
        # Runtime 레이블 
        lbl_runtime_title = QLabel("Runtime :")
        lbl_runtime_title.setObjectName("info_title")
        self.lbl_runtime_val = QLabel("00 : 00 : 00")
        self.lbl_runtime_val.setObjectName("info_value")

        # 배치
        info_layout.addStretch(1) # 우측 정렬 효과
        info_layout.addWidget(lbl_runtime_title)
        info_layout.addWidget(self.lbl_runtime_val)
        
        # 그룹 레이아웃의 맨 위에 추가
        group_layout.addLayout(info_layout)

        # 상단과 하단을 벌려주는 스프링
        # info_layout은 위로, bottom_layout은 아래로
        group_layout.addStretch(1)

        # 1. file_layout와 control_layout를 좌우로 나란히 놓기 위한 부모 레이아웃
        bottom_layout = QHBoxLayout()


        # --- 2. 왼쪽: 파일 로드 (LOAD 버튼 + 파일명) --- #
        file_layout = QHBoxLayout()
        
        # LOAD 버튼
        self.btn_load = QPushButton("LOAD")
        self.btn_load.setFixedSize(60, 30)
        self.btn_load.setProperty("type", "general") # 공통 보라색 버튼 스타일 적용

        # 파일명 레이블
        self.lbl_filename = QLabel("FileName...")
        self.lbl_filename.setObjectName("filename_label")
        
        # 배치: LOAD버튼 - (간격) - 파일명 - (스프링)
        file_layout.addWidget(self.btn_load)
        file_layout.addSpacing(15)
        file_layout.addWidget(self.lbl_filename)
        file_layout.addStretch(1) # 왼쪽 정렬 유지


        # --- 3. 오른쪽: 제어 버튼 (START, STOP) --- #
        control_layout = QHBoxLayout()
        
        # START 버튼
        self.btn_start = QPushButton("START")
        self.btn_start.setFixedSize(70, 30)
        self.btn_start.setProperty("type", "general")

        # STOP 버튼
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setFixedSize(70, 30)
        self.btn_stop.setProperty("type", "general")

        # 배치: (스프링) - START - (간격) - STOP
        control_layout.addStretch(1) # 우측 정렬 효과
        control_layout.addWidget(self.btn_start)
        control_layout.addSpacing(10)
        control_layout.addWidget(self.btn_stop)

        # 4. bottom_layout 안에 file_layout과 control_layout을 좌우로 배치
        bottom_layout.addLayout(file_layout)
        bottom_layout.addLayout(control_layout)

        # bottom_layout를 그룹 레이아웃에 추가
        group_layout.addLayout(bottom_layout)

        # 전체 레이아웃에 그룹박스 추가
        main_layout.addWidget(base_group_box)

    def _bind_events(self):
        """
        전선 연결하기 (아직 불 들어온것 아님)
            - 누가 누구랑 연결될 지 미리 정해주기
            - 앱이 시작될 때 딱 1번만 호출
        시그널-슬롯(_on으로 시작하는 메서드) connect를 모아놓음 - 버튼 눌리면 어떤 일을 할 지 약속

        # Pylance 경고 해결 위해 if문 추가
        """

        if self.btn_load: self.btn_load.clicked.connect(self._on_load_clicked)      # LOAD 연결
        if self.btn_start: self.btn_start.clicked.connect(self._on_start_clicked)   # START 연결
        if self.btn_stop: self.btn_stop.clicked.connect(self._on_stop_clicked)      # STOP 연결


    # ===============================================
    # 데이터 처리
    # ===============================================
    # ===============================================
    # 데이터 처리
    # ===============================================
    def update_data(self, data: Dict[str, Any]):
        """
        데이터(dict)를 받아 UI 업데이트
            BaseWidget의 update_data()를 통해 호출됨
        
        Args:
            data (dict): {'is_busy': True/False}
        """

        # 상태에 따른 활성화/비활성화 (BaseWidget 기능 활용)
        if 'is_busy' in data:
            self._is_servo_busy = data['is_busy']  # 서보 busy 상태 저장
            self._update_button_state()            # 버튼 상태 갱신 (서보 바쁨 or 시퀀스 실행 중)

    @pyqtSlot(bool)
    def _update_running_state(self, is_running: bool):
        """뷰모델에서 '시퀀스 실행 중' 상태 변경 알림"""
        self._is_sequence_running = is_running
        self._update_button_state()
    
    def _update_button_state(self):
        """
        START, LOAD 버튼의 활성화 여부 결정
        조건: (시퀀스 실행 중 OR 서보 바쁨)이면 비활성화
        """
        should_disable = self._is_sequence_running or self._is_servo_busy
        
        # 로봇이 바쁘거나 실행 중 -> START, LOAD 비활성화
        if self.btn_start: self.btn_start.setEnabled(not should_disable)
        if self.btn_load: self.btn_load.setEnabled(not should_disable)
        
        # STOP 버튼은 언제나 활성화 (비상 정지용)
        if self.btn_stop: self.btn_stop.setEnabled(True)

    def clear_widget(self):
        """
        초기 상태로 리셋 (BaseWidget.clear_widget 오버라이드)
            깨끗하게 화면 지우기
        """
        EVENT_BUS.log.message.emit(f"{self.log_prefix} UI 초기화", "DEBUG")
        
        # 내부 상태 초기화
        self._is_sequence_running = False
        self._is_servo_busy = False

        # UI 텍스트 초기화
        if self.lbl_filename:       self.lbl_filename.setText("FileName...")
        if self.lbl_runtime_val:    self.lbl_runtime_val.setText("00 : 00 : 00")
        
        # 버튼 활성화 복구
        self._update_button_state()
        if self.btn_stop: self.btn_stop.setEnabled(True)
        
        # 부모 클래스의 초기화(데이터 비우기) 호출
        super().clear_widget()


    # ===============================================
    # 이벤트 핸들러 (Slots)
    #   - 사용자 입력(클릭, 선택)에 대한 반응 처리
    # ===============================================    
    @pyqtSlot()
    def _on_load_clicked(self):
        self._handle_load_file_button_clicked()

    @pyqtSlot()
    def _on_start_clicked(self):
        self._handle_start_button_clicked()

    @pyqtSlot()
    def _on_stop_clicked(self):
        """STOP 버튼 클릭 핸들러"""
        EVENT_BUS.log.message.emit(f"{self.log_prefix} STOP 버튼 클릭됨", "INFO")

        if self.vm:
            # 뷰모델에게 멈추라고 요청 (타이머 정지 & 로봇 정지)
            self.vm.stop_sequence()


    # --- [처리] UI 차원에서 해야 할 일 --- #
    @pyqtSlot()
    def _handle_load_file_button_clicked(self):
        """ 
        'LOAD' 버튼이 클릭되면 
            1. 파일을 선택 다이얼로그 표시
            2. 선택된 파일이름 표시
            3. 선택된 파일 VM에 전달
        """
        if not self.vm:
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 뷰모델이 연결되지 않았습니다.", "WARNING")
            return

        """
        # QFileDialog를 사용하여 문자열 경로 획득
        file_path_result = QFileDialog.getOpenFileName(
            self,
            "시퀀스 파일 선택",
            "/",
            "시퀀스 파일 (*.csv)"
        )

        if not file_path_result or not file_path_result[0]:
            EVENT_BUS.log.message.emit("파일 선택이 취소되었습니다.", "INFO")
            return

        file_path_str = file_path_result[0]
        """

        file_path_str = "D:/WORKSPACE/Projects_Dex/kriss_robot_sync/_for_tests_on_the_field/테스트용데이터/sequence_sample.csv"
        file_path_obj = Path(file_path_str)

        if self.lbl_filename:
            self.lbl_filename.setText(file_path_obj.name)

        EVENT_BUS.log.message.emit(f"파일 선택됨: {file_path_obj}", "INFO")
        
        # Path 객체를 VM의 슬롯으로 전달
        self.vm.load_sequence_data(file_path_obj)

    def _handle_start_button_clicked(self):
        """
        START 버튼 클릭 시: 파일이 로드되었는지 확인하고 VM에 시퀀스 시작을 요청
        """
        # 방어코드 - 뷰모델 없으면
        if not self.vm: return
        # 방어 코드 - 읽은 파일이 없으면 뷰모델 호출 안 함
        if self.lbl_filename is None or self.lbl_filename.text() == "FileName..." or not self.lbl_filename.text(): return

        EVENT_BUS.log.message.emit(f"{self.log_prefix} START 버튼 클릭됨 - 작업 시작 요청", "INFO")

        self.vm.start_sequence()







# ==========================================================
# Smoke Test
"""
python -m ui.widgets.task_manager_widget
"""
# ==========================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    from config.paths import STYLESHEET_PATH
    from styles.style_manager import load_and_apply_stylesheet
    from core.log_listener import LogListener

        # [중요] DLL 로드
    from utils.dll_loader import load_pyads_dll
    try:
        load_pyads_dll()
        print("✅ DLL 로드 완료")
    except Exception as e:
        print(f"⚠️ DLL 로드 실패: {e}")

    from view_models.task_manager_viewmodel import TaskManagerViewModel
    from services.sequence_service import SequenceService


    app = QApplication(sys.argv)

    listener = LogListener()

    service = SequenceService()
    vm = TaskManagerViewModel(service) # type: ignore


    # 스타일시트 파일 로드 및 적용
    load_and_apply_stylesheet(app, STYLESHEET_PATH)

    # 윈도우 생성 및 테스트
    window = TaskManagerWidget(vm)
    window.resize(450, 200) # 요청하신 비율을 확인하기 적당한 크기
    window.show()

    sys.exit(app.exec())