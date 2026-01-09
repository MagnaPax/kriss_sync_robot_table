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

        # 1. 헤더/라벨 (옵션)
        # title_label = QLabel("SYSTEM CONTROL")
        # title_label.setStyleSheet("font-weight: bold; color: #555;")
        # layout.addWidget(title_label)

        # 2. 비상 정지 버튼
        self.stop_btn = QPushButton("EMERGENCY STOP")
        self.stop_btn.setObjectName("emergency_button") # QSS 스타일 적용 (#DC3545 Red)
        
        # 버튼 스타일 강화 (크게 만들기)
        self.stop_btn.setMinimumHeight(60)
        font = QFont()
        font.setBold(True)
        font.setPointSize(16)
        self.stop_btn.setFont(font)
        
        # 아이콘 추가 (있다면)
        # self.stop_btn.setIcon(QIcon("resources/icons/stop.png"))
        # self.stop_btn.setIconSize(QSize(32, 32))

        # 클릭 이벤트 연결
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        
        layout.addWidget(self.stop_btn)

        # 3. 설명 텍스트 (작게)
        desc_label = QLabel("Click to halt all robot & servo motions immediately.")
        desc_label.setStyleSheet("color: #777; font-size: 11px; font-style: italic;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

    def set_view_model(self, vm: "MainViewModel"):
        """
        비상 정지는 시스템 전체를 멈추는 전역적인(Global) 명령.
        시스템 전체의 생명주기와 상태를 관리하는 MainViewModel에 주입되는게 좋음
        """
        self.vm = vm

    @pyqtSlot()
    def _on_stop_clicked(self):
        """비상 정지 버튼 클릭 핸들러"""
        if hasattr(self, 'vm') and self.vm:
            # ViewModel에게 비상 정지 요청
            # 비상 정지 기능 하나를 위해 전용 뷰모델을 만드는 것은 YAGNI 원칙에 위배된다
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
