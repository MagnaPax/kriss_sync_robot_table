# styles/style_manager.py
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QApplication
from utils.file_handler import load_text



def load_and_apply_stylesheet(target: QWidget | QApplication, path: Path) -> None:
    """
    스타일시티(QSS) 파일을 읽어 적용

    Args:
        target: 스타일을 적용할 위젯 또는 QApplication 객체.
        path: 읽어올 QSS 파일의 경로
    """

    # 스타일시트 읽기 - qss 파일의 형태는 텍스트 문자열
    stylesheet_content = load_text(path)

    # 타겟에 가져온 스타일시트 적용
    target.setStyleSheet(stylesheet_content)


def apply_theme(app: QApplication, theme_name='default'):
    """테마 관리 기능(다크/라이트 모드)"""

    # TODO: 테마 관리 기능 추가하기
