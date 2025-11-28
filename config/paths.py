# config/paths.py
"""경로 정보"""
from pathlib import Path



# 프로젝트 루트 (현재 파일의 부모의 부모) -> config/paths.py -> config -> root
ROOT_DIR = Path(__file__).resolve().parent.parent

STYLESHEET_PATH = ROOT_DIR / "styles" / "stylesheet.qss"
CONFIG_MACRO_PATH = ROOT_DIR / "config" / "macro_settings.json"
CONFIG_INI_PATH = ROOT_DIR / "config" / "settings.ini"
LOG_DIR = ROOT_DIR / "logs"