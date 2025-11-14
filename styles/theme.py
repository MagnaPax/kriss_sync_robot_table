# styles/theme.py
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QApplication



def load_and_apply_stylesheet(target_widget: QWidget | QApplication, qss_file_path: str | Path):
    """
    지정된 QSS 파일을 읽어 target_widget 또는 QApplication 전체에 적용합니다.

    Args:
        target_widget: 스타일을 적용할 위젯 또는 QApplication 객체.
        qss_file_path: 읽어올 QSS 파일의 경로 (문자열 또는 Path 객체).
    """
    qss_path = Path(qss_file_path)
    
    if qss_path.exists():
        try:
            with open(qss_path, "r", encoding='UTF-8') as file:
                stylesheet = file.read()
                target_widget.setStyleSheet(stylesheet)
                print(f"✅ 스타일시트 로드 성공: {qss_path.name}")
                return True
        except Exception as e:
            print(f"❌ 스타일시트 로드 실패 ({qss_path.name}): {e}")
            return False
    else:
        print(f"⚠️ 스타일시트 파일 없음: {qss_path}")
        return False

# (선택 사항) 테마 관리 기능 추가 (다크/라이트 모드 등)
# def apply_theme(app: QApplication, theme_name='default'):
#     qss_file = f"styles/{theme_name}_stylesheet.qss"
#     load_and_apply_stylesheet(app, qss_file)