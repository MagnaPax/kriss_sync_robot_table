import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from pathlib import Path
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt


class LogoWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- 경로 ---
        logo_path = Path("resources/images/kriss_logo.gif")
        logo_pixmap = QPixmap(str(logo_path.resolve()))     # Path객체 대신 문자열 경로


        # --- 이미지 ---
        # QPixmap 는 위젯이 아니다
        # QPixmap 는 이미지 데이터를 담는 그래픽 리소스 객체
        # QLabel '위젯'에 담아서 표시 ➡️ QPixmap: 그림, QLabel: 캔버스
        scaled_pixmap = logo_pixmap.scaledToWidth(161, Qt.TransformationMode.SmoothTransformation)  # 이미지 크기 바꿈
        lbl_img = QLabel()                                  # 레이블 생성
        lbl_img.setPixmap(scaled_pixmap)                    # 레이블에 표시될 이미지로 scaled_pixmap 설정
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 가운데 정렬


        # --- 이미지 크기 표시 레이블 ---
        lbl_size_img = QLabel(f'Width: {scaled_pixmap.width()}, Height: {scaled_pixmap.height()}')  # 이미지 크기 표시 레이블
        lbl_size_img.setAlignment(Qt.AlignmentFlag.AlignCenter)


        # --- 위젯에 레이아웃 적용 ---
        layout = QVBoxLayout(self)  # 수직 레이아웃 생성
        layout.addWidget(lbl_img)   # 레이아웃에 이미지 레이블 추가
        layout.addWidget(lbl_size_img)  # 레이아웃에 크기 레이블 추가






# --- 단독 실행을 위한 테스트 코드 ---
if __name__ == '__main__':
    # 이 파일을 직접 실행할 때만 아래 코드 동작
    app = QApplication(sys.argv)
    
    window = LogoWidget()
    window.setWindowTitle("테스트")
    window.show()
    
    sys.exit(app.exec())
