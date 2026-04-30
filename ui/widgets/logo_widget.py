import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from pathlib import Path
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from typing import Optional

from core.settings import SETTINGS

class LogoWidget(QWidget):

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # --- 경로 ---
        logo_path = Path(SETTINGS.app.kriss_ci_path)
        logo_pixmap = QPixmap(str(logo_path.resolve()))     # Path객체 대신 문자열 경로


        # --- 이미지 ---
        # QPixmap 는 위젯이 아니다
        # QPixmap 는 이미지 데이터를 담는 그래픽 리소스 객체
        # QLabel '위젯'에 담아서 표시 ➡️ QPixmap: 그림, QLabel: 캔버스
        scaled_pixmap = logo_pixmap.scaledToWidth(161, Qt.TransformationMode.SmoothTransformation)  # 이미지 크기 바꿈
        lbl_img = QLabel()                                  # 레이블 생성
        lbl_img.setPixmap(scaled_pixmap)                    # 레이블에 표시될 이미지로 scaled_pixmap 설정
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 가운데 정렬


        # --- 레이아웃 ---
        layout = QVBoxLayout(self)  # 수직 레이아웃 생성

        layout.addStretch(1)        # 위젯 위쪽에 빈 공간 추가
        layout.addWidget(lbl_img)   # 이미지 레이블 추가
        layout.addStretch(1)        # 위젯 아래에 빈 공간 추가





# --- 단독 실행을 위한 테스트 코드 ---
if __name__ == '__main__':
    # 이 파일을 직접 실행할 때만 아래 코드 동작
    app = QApplication(sys.argv)
    
    window = LogoWidget()
    window.setWindowTitle("테스트")
    window.setStyleSheet("background-color: grey;")  # 레이아웃 확인을 위한 배경색
    window.show()
    
    sys.exit(app.exec())
