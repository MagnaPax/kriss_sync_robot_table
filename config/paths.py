# config/paths.py
"""경로 정보"""
from pathlib import Path



# 프로젝트 루트 (현재 파일의 부모의 부모) -> config/paths.py -> config -> root
ROOT_DIR = Path(__file__).resolve().parent.parent


# 기본 설정값(앱, TwinCAT, Robot, Servo 등)
CONFIG_INI_PATH = ROOT_DIR / "config" / "settings.ini"

# DLL 파일 경로 (libs 폴더)
TC_ADS_DLL_PATH = ROOT_DIR / "libs" / "TcAdsDll.dll"

# 스타일시트
STYLESHEET_PATH = ROOT_DIR / "styles" / "stylesheet.qss"

# 사용자 입력 매크로값 저장
CONFIG_MACRO_PATH = ROOT_DIR / "config" / "macro_settings.json"

# 로그파일 저장 경로
LOG_DIR = ROOT_DIR / "logs"

# 사용자 마지막 상태 저장 (윈도우 위치, 마지막 열었던 폴더 등)
USER_STATE_PATH = ROOT_DIR / "config" / "user_state.ini"
