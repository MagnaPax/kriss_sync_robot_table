# utils/env.py
import sys, os
from enum import Enum
from pathlib import Path



class Environment(Enum):
    """실행 환경 표시"""
    DEVELOPMENT = "as_Development"
    PRODUCTION = "as_Published"


def is_packaged() -> bool:
    """
    앱이 패키징된 실행 파일인지 판단

    판단 기준:
    1. sys.frozen == True → PyInstaller(윈도우), cx_Freeze(맥OS) 등으로 패키징된 경우
    2. 실행 파일이 Windows용 .exe
    3. 강제 개발 모드 탐지
    """

    # 1. 패키징 도구 감지
    """
    getattr(object, name, default) 함수:
        sys 모듈에서 'frozen'이라는 꼬리표를 찾은 뒤 없으면 AttributeError 에러 대신 그냥 False

    frozen 속성:
        PyInstaller나 cx_Freeze 같은 프로그램으로 파이썬 스크립트를 하나의 실행 파일(.exe)로 "얼릴" 때, 
        이 프로그램들이 sys 모듈에 frozen = True 라는 꼬리표를 붙인다
        그러므로 sys.frozen이라는 꼬리표가 있으면 얼려진 상태(실행 파일)를 나타낸다
    """
    if getattr(sys, 'frozen', False):
        return True
    
    # 2. 실행파일이 Windows 운영체제인지
    if sys.platform == "win32" and os.path.splitext(sys.executable)[1] == ".exe":
        return True

    # 3. 강제 개발 모드 탐지
    """
    환경변수가 DEV_MODE=1 이면 실행파일이더라도 강제로 개발모드로 동작

    [🧩개발 모드로 강제 실행 방법]
    $ set DEV_MODE=1
    $ python main.py

    [🚀패키징 모드로 실행 방법]
    $ del DEV_MODE
    $ ./kriss_robot_sync.ex
    """
    if os.getenv("DEV_MODE") == "1":
        return False
    
    return False


def get_environment() -> Environment:
    """개발 환경인지 배포 환경인지 반환"""
    return Environment.PRODUCTION if is_packaged() else Environment.DEVELOPMENT


def get_environment_base_path() -> Path:
    """
    모드(개발/배포) 기준 절대 경로 반환
    - 패키징: 실행 파일이 있는 폴더
    - 개발: 프로젝트 루트 (현재 파일의 부모 부모)
    """    
    if is_packaged():
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parent.parent
