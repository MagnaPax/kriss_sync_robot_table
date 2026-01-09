# ui/widgets/emergency_stop_widget.py
from PyQt6.QtWidgets import QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from PyQt6.QtCore import pyqtSlot, QSize
from PyQt6.QtGui import QIcon, QFont
from typing import TYPE_CHECKING, Any

from ui.widgets.base_widget import BaseWidget

if TYPE_CHECKING:
    from view_models.main_window_viewmodel import MainViewModel


class EmergencyStopWidget(BaseWidget):
    """
    [비상 정지 위젯]
    - 로봇과 서보 모터를 즉시 정지시키는 큰 버튼 제공
    - BaseWidget 상속으로 일관성 유지
    """

    def _init_ui(self):
        """UI 구성"""
        # 레이아웃 설정
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 비상 정지 버튼
        self.stop_btn = QPushButton("EMERGENCY STOP")
        self.stop_btn.setObjectName("emergency_button") # QSS(#emergency_button)
        
        # 클릭 이벤트 연결
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        
        layout.addWidget(self.stop_btn)


    def set_view_model(self, vm: "MainViewModel"):
        """
        비상 정지는 시스템 전체를 멈추는 전역적인(Global) 명령이기 때문에
        시스템 전체의 생명주기와 상태를 관리하는 MainViewModel에 주입되는게 좋음
        """
        self.vm = vm

    @pyqtSlot()
    def _on_stop_clicked(self):
        """비상 정지 버튼 클릭 핸들러"""
        if hasattr(self, 'vm') and self.vm:
            # ViewModel에게 비상 정지 요청
            # 비상 정지 기능 하나를 위해 전용 뷰모델을 따로 만드는 것은 YAGNI 원칙에 위배된다
            self.vm.emergency_stop()
        else:
            print("Error: ViewModel not set for EmergencyStopWidget")

    def update_data(self, data: Any) -> None:
        """
        데이터 업데이트 (BaseWidget 필수 구현)
        - 비상 정지 위젯은 표시할 데이터가 딱히 없으므로 pass
        - 필요하다면 '현재 비상정지 상태인가?'를 표시할 수도 있음
        """
        pass

"""
python -m ui.widgets.emergency_stop_widget
"""
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    import os
    
    # 프로젝트 루트 경로를 sys.path에 추가 (styles 모듈 import 위함)
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    from styles.style_manager import load_and_apply_stylesheet

    app = QApplication(sys.argv)
    
    # 실제 QSS 파일 로드 및 적용
    # load_and_apply_stylesheet 함수는 (app, path) 두 개의 인자를 받습니다.
    # 현재 파일 위치: ui/widgets/emergency_stop_widget.py -> 상위3번 -> 프로젝트 루트
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    qss_path = os.path.join(project_root, "styles", "stylesheet.qss")
    
    load_and_apply_stylesheet(app, qss_path)

    widget = EmergencyStopWidget()
    widget.show()

    sys.exit(app.exec())
