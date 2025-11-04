# utils/logger.py
"""
utils/logger.py
----------------
중앙 로깅 설정 모듈.
모든 모듈에서 import 해서 사용:
    from utils.logger import logger
"""
import logging
import os, sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path



APP_NAME = "KRISSRobotPolisherSync"
APP_AUTHOR = "Dexterous_Technology"


if getattr(sys, 'frozen', False):
    """
    getattr(object, name, default) 함수:
        sys 모듈에서 'frozen'이라는 꼬리표를 찾은 뒤 없으면 AttributeError 에러 대신 그냥 False

    frozen 속성:
        PyInstaller나 cx_Freeze 같은 프로그램으로 파이썬 스크립트를 하나의 실행 파일(.exe)로 "얼릴" 때, 
        이 프로그램들이 sys 모듈에 frozen = True 라는 꼬리표를 붙인다
        그러므로 sys.frozen이라는 꼬리표가 있으면 얼려진 상태(실행 파일)를 나타낸다

    [시나리오]
    1. 배포 환경:
        True 반환 - if 실행

    2. 개발 환경:
        False 반환 - else 실행
    """

    # 배포 환경: PyInstaller, cx_Freeze 등으로 패키징된 경우
    from platformdirs import user_data_dir
    LOG_DIR = Path(user_data_dir(APP_NAME, APP_AUTHOR))     #  배포된 OS 표준 사용자 데이터 폴더
else:
    # 개발 환경
    LOG_DIR = Path(__file__).parent.parent / "logs"         # 이 파일의 조상 폴더 밑에 logs 폴더

# 폴더 생성
# parents=True: 필요한 모든 상위 디렉터리 생성
# exist_ok=True: 디렉터리가 이미 있어도 오케이
LOG_DIR.mkdir(parents=True, exist_ok=True)
