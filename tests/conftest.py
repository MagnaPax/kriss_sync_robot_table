# tests/conftest.py
"""pytest의 설정 파일인 동시에 테스트 도우미"""
import sys
import pytest
from PyQt6.QtWidgets import QApplication    # GUI 앱을 관리하는 총괄 관리자 클래스 임포트
from utils.dll_loader import load_pyads_dll # pyads를 위한 dll 로더


# 테스트 시작 전 DLL 로드 (Windows OS 에서만)
try:
    load_pyads_dll()
except Exception as e:
    print(f"⚠️ [Test Setup] DLL 로드 실패 (Mock 테스트라면 무시 가능): {e}")




"""
픽스처 설정
    모든 테스트가 공유하는 '가짜 앱' 준비물
    -> 아래에 정의된 함수(qapp)를 테스트용 준비물(Fixture)로 등록한다

scope   : 이 픽스처의 수명을 결정
session : 테스트 전체(모든 파일)를 통틀어 딱 한 번만 만들고 계속 재사용. (PyQt에 필수)
        -> 테스트가 100개든 1000개든 QApplication은 맨 처음에 딱 한 번만 켜라
"""
@pytest.fixture(scope="session")


def qapp():
    """
    픽스처 함수

        테스트를 시작할 때 QApplication을 딱 한 번만 안전하게 생성해서
        모든 테스트 함수들이 돌려쓸 수 있게 해주는 공용 보급소
    """

    # QApplication 생성
    # 테스트 때마다 QApplication을 만들고 지우면 에러가 나기 때문에 여기서 한 번만 만들어 준다
    app = QApplication.instance()

    # (방어코드) 만들어진 QApplication가 있는지 확인
    if app is None:
        app = QApplication(sys.argv)    # 앱 인스턴스를 생성

    # 값을 테스트 함수에게 빌려주고 잠시 대기
    # 모든 테스트가 다 끝나면 yield 뒷부분의 코드가 실행
    yield app
