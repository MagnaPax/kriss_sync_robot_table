# ui/__init__.py
"""
UI 모듈 초기화
- KRISS의 "다축 제어기 H/W Upgrade 및 EtherCAT을 이용한 동기화 시스템 개발" 프로젝트
- 사용자 인터페이스 관련 클래스 제공
- MainWindow, 위젯, 패널, 다이얼로그를 포함
- 작성자: 한천희
- 버전: 0.1.0 (2025.10.17, 초기 설정)
"""

from .main_window import MainWindow

__all__ = ['MainWindow']
