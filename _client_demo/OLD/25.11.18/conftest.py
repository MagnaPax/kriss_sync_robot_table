# _client_demo/25.11.18/conftest.py

"""
tests 폴더만 지정해서 실행
_client_demo/25.11.18/pytest tests/
"""
import sys
import os
import ctypes
import pathlib
import pytest
from PyQt6.QtWidgets import QApplication
from typing import Any, Optional

# --- 1. 경로 설정 ---
# 이 conftest.py 파일이 있는 폴더(현재 작업 폴더)를 sys.path에 추가
current_dir = pathlib.Path(__file__).parent
sys.path.insert(0, str(current_dir))

# --- 2. DLL 로더 (즉시 실행을 위해 수정됨) ---
pyads_module: Optional[Any] = None


def load_pyads_dll_for_test() -> bool:
    """
    테스트 세션 시작 시 DLL을 로드합니다.
    이 함수는 pytest 수집 단계에서 모듈들이 임포트되기 전에 실행되어야 합니다.
    """
    global pyads_module
    if pyads_module:
        return True
    
    # TcAdsDll.dll 파일이 이 폴더(conftest.py와 같은 위치)에 있어야 함
    dll_path = current_dir / "TcAdsDll.dll"

    try:
        print(f"\n[Pytest] DLL 로드 시도: {dll_path}")
        # 1. DLL 로드
        ctypes.WinDLL(str(dll_path))
        # 2. 검색 경로 추가
        os.add_dll_directory(str(current_dir))
        
        # 3. pyads 모듈 임포트 시도
        import pyads
        pyads_module = pyads
        
        print("✅ [Pytest] DLL 및 pyads 모듈 로드 성공.")
        return True
    except (OSError, ImportError, FileNotFoundError) as e:
        print(f"❌ [Pytest] DLL 로드 실패: {e}")
        return False

# [중요] 픽스처가 실행되기 전에, 파일이 로드되자마자 DLL 경로를 설정합니다.
# 이렇게 해야 test_viewmodel.py가 임포트될 때 pyads 에러가 나지 않습니다.
if not load_pyads_dll_for_test():
    print("⚠️ 경고: TcAdsDll.dll 로드에 실패했습니다. 관련 테스트가 실패할 수 있습니다.")

# --- 3. Pytest Fixtures ---

@pytest.fixture(scope="session", autouse=True)
def app_context():
    """
    테스트 세션 전체에서 단 한 번 실행:
    QApplication을 생성 (Qt 테스트에 필수)
    """
    # 이미 위에서 로드 시도를 했으므로 여기서는 확인만 함
    if not pyads_module:
        pytest.fail("TcAdsDll.dll 로드 실패. 테스트를 진행할 수 없습니다.")
    
    app = QApplication.instance() or QApplication(sys.argv)
    yield app
    app.quit()

@pytest.fixture(scope="module")
def real_model(app_context):
    """[모듈 스코프] 실제 FanucController 인스턴스를 생성"""
    from fanuc_logic import FanucController
    return FanucController()

@pytest.fixture(scope="module")
def mock_model(app_context):
    """[모듈 스코프] MockFanucController 인스턴스를 생성"""
    from mock_model import MockFanucController
    return MockFanucController()

@pytest.fixture(scope="function")
def viewmodel(real_model, mock_model):
    """
    [함수 스코프] 각 테스트 함수마다 새로운 ViewModel을 생성
    """
    from viewmodel import FanucViewModel
    vm = FanucViewModel(real_model, mock_model)
    return vm