# ui/widgets/target_position_widget.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QGroupBox, QLabel

from ui.widgets.base_widget import BaseWidget



class TargetPositionWidget(BaseWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("target_position_widget")

        # 메인 레이아웃(세로 정렬)을 TargetPositionWidget(self)에 설정
        # 이 레이아웃이 전체 위젯의 크기를 관리한다
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

        # 모든 부속 위젯을 담을 그룹박스 생성
        group_box = QGroupBox("Target Position")
        group_box.setStyleSheet("QGroupBox { background-color: #E0E0E0; }") # 개발용 임시 배경 스타일
        main_layout.addWidget(group_box) # 메인 레이아웃이 그룹박스를 채우도록 추가







# ==========================================================
# 2. 단독 실행 (테스트용)
"""
python -m ui.widgets.target_position_widget
"""
# ==========================================================
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    
    # 배경 확인을 위한 메인 윈도우
    main_win = QMainWindow()
    widget = TargetPositionWidget()
    main_win.setCentralWidget(widget)
    main_win.setWindowTitle("TargetPositionWidget 테스트")
    main_win.resize(400, 300)
    main_win.show()
    
    sys.exit(app.exec())
