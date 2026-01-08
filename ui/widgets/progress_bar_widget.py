from PyQt6.QtWidgets import QVBoxLayout, QProgressBar, QLabel
from PyQt6.QtCore import Qt
from typing import Any

from ui.widgets.base_widget import BaseWidget
from view_models.progress_bar_viewmodel import ProgressBarViewModel


class ProgressBarWidget(BaseWidget):
    """진행률 표시 위젯"""

    def __init__(self, viewmodel: ProgressBarViewModel):
        self.vm = viewmodel
        super().__init__()  # BaseWidget 초기화 (내부적으로 _init_ui 호출)
        
        self._bind_viewmodel()

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
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

    def _bind_viewmodel(self):
        """ViewModel 시그널 연결"""
        self.vm.progress_range_changed.connect(self.progress_bar.setRange)
        self.vm.progress_value_changed.connect(self.progress_bar.setValue)
        self.vm.progress_status_changed.connect(self.status_label.setText)

    def update_data(self, data: Any) -> None:
        """
        BaseWidget 추상 메서드 구현
        (이 위젯은 ViewModel 시그널로 동작하므로 직접 호출될 일은 없으나 구현은 필수)
        """
        pass


# ==========================================================
# 3. 단독 실행 (테스트용)
"""
python -m ui.widgets.progress_bar_widget
"""
# ==========================================================
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    from styles.style_manager import load_and_apply_stylesheet
    from pathlib import Path

    # QApplication 생성
    app = QApplication(sys.argv)
    
    # 스타일시트 로드 및 적용
    load_and_apply_stylesheet(app, Path("styles/stylesheet.qss"))

    # ViewModel 및 Widget 생성
    vm = ProgressBarViewModel()
    widget = ProgressBarWidget(vm)
    
    # 윈도우 설정
    widget.setWindowTitle("Progress Bar Smoke Test")
    widget.resize(400, 100)
    widget.show()

    # 테스트 초기 데이터 설정
    vm._on_sequence_data_loaded(["item"] * 100) # 100개 아이템

    # 동적 진행률 시뮬레이션
    current_value = 0
    direction = 1 # 1: 증가, -1: 감소

    def update_progress():
        global current_value, direction
        
        current_value += direction
        
        # 방향 전환 로직 (0 ~ 100 사이 왕복)
        if current_value >= 100:
            direction = -1
        elif current_value <= 0:
            direction = 1
            
        vm._on_progress_updated(current_value, 100, "Processing...")

    # 타이머 설정 (50ms마다 업데이트 = 20fps)
    timer = QTimer()
    timer.timeout.connect(update_progress)
    timer.start(50)

    print("🚀 Smoke Test 시작: 프로그레스 바가 왕복 운동합니다.")
    print("종료하려면 창을 닫으세요.")

    sys.exit(app.exec())
