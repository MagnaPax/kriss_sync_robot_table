from PyQt6.QtWidgets import QVBoxLayout, QProgressBar, QLabel, QWidget
from PyQt6.QtCore import Qt
from typing import Any, Optional, TYPE_CHECKING

from ui.widgets.base_widget import BaseWidget

if TYPE_CHECKING:
    from view_models.progress_bar_viewmodel import ProgressBarViewModel


class ProgressBarWidget(BaseWidget):
    """진행률 표시 위젯 (MVVM 아키텍처 적용)"""

    def __init__(self, parent: Optional[QWidget] = None):
        # UI 요소 참조를 초기화 (안전한 접근을 위해)
        self.status_label: Optional[QLabel] = None
        self.progress_bar: Optional[QProgressBar] = None
        self.vm: Optional["ProgressBarViewModel"] = None
        
        super().__init__(parent)  # BaseWidget 초기화 -> _init_ui 호출
        
        # 내부 위젯 이벤트 바인딩 (현재는 없음)
        self._bind_events()

    def set_view_model(self, view_model: "ProgressBarViewModel"):
        """ViewModel 주입 및 시그널 연결 (Dependency Injection)"""
        # 1. 기존 뷰모델 연결 안전하게 해제
        if self.vm and self.progress_bar and self.status_label:
            try:
                self.vm.progress_range_changed.disconnect(self.progress_bar.setRange)
                self.vm.progress_value_changed.disconnect(self.progress_bar.setValue)
                self.vm.progress_status_changed.disconnect(self.status_label.setText)
            except (TypeError, RuntimeError):
                # 이미 끊겨있거나 객체가 파괴된 경우 무시
                pass
        
        # 2. 새로운 뷰모델 주입
        self.vm = view_model
        
        # 3. 데이터 바인딩 실행
        self._bind_vm_signals()

    def _init_ui(self):
        """UI 구성 (BaseWidget 추상 메서드 구현)"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 상태 메시지 레이블
        self.status_label = QLabel("No Job")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; color: #555;")
        
        # 프로그레스 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setObjectName("main_progress_bar")
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

    def _bind_events(self):
        """위젯 내부 UI 구성요소의 이벤트 연결 (Internal Event Binding)"""
        # 현재 ProgressBarWidget은 버튼 클릭 등 내부 입력 이벤트가 없음
        pass

    def _bind_vm_signals(self):
        """ViewModel로부터 전달되는 데이터 시그널 연결 (External Data Binding)"""
        if not self.vm or not self.progress_bar or not self.status_label:
            return
        
        # 뷰모델의 상태 변화를 UI 요소에 직접 연결
        self.vm.progress_range_changed.connect(self.progress_bar.setRange)
        self.vm.progress_value_changed.connect(self.progress_bar.setValue)
        self.vm.progress_status_changed.connect(self.status_label.setText)

    def update_data(self, data: Any) -> None:
        """
        BaseWidget 추상 메서드 구현
        (주로 ViewModel 시그널로 동작하지만, 외부에서 직접 데이터를 밀어넣을 때 사용)
        """
        if not (self.status_label and self.progress_bar):
            return

        if isinstance(data, dict):
            if 'status' in data: self.status_label.setText(str(data['status']))
            if 'value' in data: self.progress_bar.setValue(int(data['value']))
            if 'range' in data: self.progress_bar.setRange(*data['range'])

