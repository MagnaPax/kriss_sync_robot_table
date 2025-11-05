# utils/env.py
import sys, os
import logging

from enum import Enum
from pathlib import Path



class Environment(Enum):
    """실행 환경 표시"""
    DEVELOPMENT = "as_Development"
    PRODUCTION = "as_Published"


class LogLevel(Enum):
    """로그 레벨"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL
    NOTSET = logging.NOTSET


class AppEnv:
    
    # 싱글톤 디자인 패턴
    _instance = None        # AppEnv 클래스의 유일한 인스턴스(객체)를 저장하기 위한 공간
    _initialized = False    # 초기화 코드가 여러번 실행되는 것을 방지하는 flag 변수(스위치)


    def __new__(cls, *args, **kwargs):
        """
        클래스가 앱 전체에서 단 하나의 인스턴스(객체)만 갖도록 보장하는 
        싱글톤(Singleton) 디자인 패턴 구현
        """
        # 1. 클래스 변수 _instance가 비어있는지(None) 확인
        if cls._instance is None:
            # 2. 비어있다면 (최초 호출이라면), 부모 클래스의 __new__를 호출하여
            #    새로운 인스턴스를 생성하고, 그 결과를 _instance에 저장            
            cls._instance = super().__new__(cls, *args, **kwargs)

        # 3. _instance에 저장된 인스턴스를 반환
        return cls._instance
    
    def __init__(self):
        # 초기화(__init__ 메서드)가 여러번 실행되는 것 방지
        if AppEnv._initialized:
            return
        AppEnv._initialized = True

        self.is_packaged: bool = self._is_packaged()
        self.environment: Environment = Environment.PRODUCTION if self.is_packaged else Environment.DEVELOPMENT
        self.base_path: Path = self._get_environment_base_path()

    
    def _is_packaged(self) -> bool:
        """
        앱이 패키징된 실행 파일인지 판단

        판단 기준:
        1. 강제 개발 모드 탐지
        2. sys.frozen == True → PyInstaller(윈도우), cx_Freeze(맥OS) 등으로 패키징된 경우
        """

        # 1. 강제 개발 모드 탐지 (가장 먼저 판단)
        """
        환경변수가 DEV_MODE=1 이면 실행파일이더라도 강제로 개발모드로 동작하게 됨

        [🧩개발 모드로 강제 실행 방법]
        $ set DEV_MODE=1
        $ python main.py

        [🚀패키징 모드로 실행 방법]
        $ del DEV_MODE
        $ ./kriss_robot_sync.ex
        """
        dev_mode = os.getenv("DEV_MODE", "").strip().lower()
        if dev_mode in ("1", "true", "yes"):
            return False  # exe여도 강제로 개발 모드로 실행
        
        # 2. 패키징 도구 감지
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
        
        # 3. 일반 개발 환경
        return False


    def get_environment(self) -> Environment:
        """개발 환경인지 배포 환경인지 반환"""
        return Environment.PRODUCTION if self._is_packaged() else Environment.DEVELOPMENT


    def _get_environment_base_path(self) -> Path:
        """
        모드(개발/배포) 기준 절대 경로 반환
        - 패키징: 실행 파일이 있는 폴더
        - 개발: 프로젝트 루트 (현재 파일의 부모 부모)
        """    
        if self._is_packaged():
            return Path(sys.executable).resolve().parent
        else:
            return Path(__file__).resolve().parent.parent       # 현재 파일의 상위 2단계


# --- 사용 편의성을 위한 전역 인스턴스 ---
app_env = AppEnv()





# ==========================================================
# 단독 실행 (테스트용)
# ==========================================================
if __name__ == "__main__":

    env = app_env.environment.value
    base_path = app_env.base_path
    is_packaged = app_env.is_packaged

    print(f"🧭 실행 환경: {env}")
    print(f"📁 베이스 경로: {base_path}")
    print(f"🧩 패키징 여부 {is_packaged}")
