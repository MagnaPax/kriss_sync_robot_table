# core/settings.py
"""
Settings (설정 관리자)
---------------------
config/settings.ini 파일을 읽어서 앱 전체에 설정값을 제공

역할:
- INI 파일 파싱
- 설정값 타입 변환 (str -> int, bool)
- 기본값(Fallback) 제공으로 파일 누락 시 안전성 확보
- 싱글톤 패턴 적용(이 클래스의 인스턴스가 앱 전체에서 사용될 수 있는 전역변수가 됨)

사용법:
    from core.settings import SETTINGS
    
    # 외부에서 마치 변수처럼 사용할 수 있다
    ams_id = SETTINGS.twincat.ams_net_id
    is_debug = SETTINGS.app.debug
"""

import configparser
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from config.paths import ROOT_DIR, CONFIG_INI_PATH




# =============================================================================
# 섹션별 데이터 클래스(데이터 그릇 만들기) - 편집기에 알려서 오타 줄일 수 있다
# =============================================================================
@dataclass
class AppConfig:
    name: str
    version: str
    debug: bool
    log_dir: Path

@dataclass
class TwinCATConfig:
    ams_net_id: str
    port: int
    demo_mode: bool

@dataclass
class RobotConfig:
    default_speed: int

@dataclass
class TurntableConfig:
    # TODO: 턴테이블 관련 설정 넣기
    pass


# =============================================================================
# Settings Manager
# =============================================================================
class Settings:
    """
    설정값을 처리하는 클래스
        앱의 어느 파일에서 불러오든 항상 똑같은 설정 객체 사용할 수 있게 제공
        그러기 위해 싱글톤 패턴 적용
    """

    _instance: Optional['Settings'] = None      # 이 클래스의 유일한 인스턴스를 담을 공간
    
    
    def __new__(cls):
        """
        생성자 함수

        이 클래스의 인스턴스가 계속 만들어지는 것을 방지하기 위해 
        부모의 생성자 메서드(object.__new__)를 오버라이딩
        """

        # 이 클래스의 인스턴스가 있으면 다시 만들지 말고 있는거 다시 써라
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize() # 여기서 딱 1번만 호출함!
        return cls._instance


    def _initialize(self):
        """
        설정 파일(settings.ini) 읽기

        __init__ 대신 _initialize 사용한 이유:
            생성자 함수(__new__)를 통해 객체가 생성되면 파이썬은 무조건 __init__ 메서드를 자동 실행
            그러면 호출 될 때 마다 __init__ 이 실행되어 설정파일을 계속 읽는다
            반면에 _initialize은 최초 생성 때 딱 한 번만 실행되서 파일을 딱 한번 읽고 끝난다
        """

        # ConfigParser 객체 생성(파이썬 내장 ini 리더기)
        # ini 파일에서 세미콜론(;) 뒤에 오는 내용은 무시하게끔
        self._config = configparser.ConfigParser(inline_comment_prefixes=';')

        # 클래스의 인스턴스로
        # 다른 파일에서 경로 정보가 필요할 때 paths.py를 다시 쓰는 대신 이 클래스만 임포트 하면 됨
        self.ROOT_DIR = ROOT_DIR
        self.CONFIG_PATH = CONFIG_INI_PATH
        
        # 설정 파일 읽기 (UTF-8)
        if CONFIG_INI_PATH.exists():
            self._config.read(self.CONFIG_PATH, encoding='utf-8')
        else:
            # 파일이 없을 경우 콘솔에 경고 (Logger가 아직 초기화 전일 수 있음)
            print(f"⚠ 경고: 설정 파일을 찾을 수 없습니다. ({self.CONFIG_PATH})")




    # ==================================================== #
    # --- 설정파일에 정의된 섹션별 접근자 (Properties) --- #
    # ==================================================== #
    """
    settings.ini의 각 섹션([Section])을 읽어 전용 데이터 클래스(@dataclass)로 포장해 반환

        설정 파일에 저장된 문자열 값을 알맞은 자료형(int, bool, Path)으로 변환
        파일 읽기가 실패했더라도 기본값이 대신 반환되도록 안전장치
        외부에서 마치 변수처럼 사용할 수 있게
    """
    @property
    def app(self) -> AppConfig:
        """[App] 섹션의 정보"""
        section = self._config['App'] if 'App' in self._config else {}

        # ini 파일 데이터를 사용. 만약 파일이 없다면 두 번째 아규먼트의 문자열을 사용
        return AppConfig(
            name=section.get('APP_NAME', 'KRISS Sync'),
            version=section.get('VERSION', '0.0.0'),
            debug=section.get('DEBUG', 'False').lower() == 'true',
            log_dir=self.ROOT_DIR / section.get('LOG_DIR', 'logs')
        )

    @property
    def twincat(self) -> TwinCATConfig:
        """[TwinCAT] 섹션의 정보"""
        section = self._config['TwinCAT'] if 'TwinCAT' in self._config else {}
        return TwinCATConfig(
            ams_net_id=section.get('AMS_NET_ID', '127.0.0.1.1.1'),
            port=int(section.get('PORT', '851')),
            demo_mode=section.get('DEMO_MODE', 'False').lower() == 'true'
        )

    @property
    def robot(self) -> RobotConfig:
        """[Robot] 섹션의 정보"""
        section = self._config['Robot'] if 'Robot' in self._config else {}
        return RobotConfig(
            default_speed=int(section.get('DEFAULT_SPEED', '50'))
        )

# 전역 인스턴스
SETTINGS = Settings()


"""
Smoke Test

python -m core.settings
"""
if __name__ == "__main__":

    from core.settings import SETTINGS

    print(f"설정 파일 경로: {SETTINGS.CONFIG_PATH}")
    print(f"Debug Mode: {SETTINGS.app.debug}")
    print(f"PLC AMS ID: {SETTINGS.twincat.ams_net_id}")
    print(f"Demo Mode: {SETTINGS.twincat.demo_mode}")