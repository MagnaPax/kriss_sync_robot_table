# tests/unit/test_main_window.py
import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import QObject, pyqtSignal
from ui.main_window import MainWindow

"""
pytest tests/unit/test_main_window.py
"""

# ------------------------------------------------------------------
# 1. 가짜 ViewModel 정의 (QObject 상속 필수)
# ------------------------------------------------------------------
class MockMainViewModel(QObject):
    """
    MainWindow가 필요로 하는 시그널과 메서드만 흉내 내는 가짜 ViewModel
    """
    # View가 구독하는 시그널들 정의
    twincat_status_data = pyqtSignal(dict)
    connection_status_changed = pyqtSignal(bool)
    show_recovery_dialog = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
    def retry_connection(self, ui_callback):
        return True # 무조건 성공한다고 가정

# ------------------------------------------------------------------
# 2. Fixture (준비물)
# ------------------------------------------------------------------
@pytest.fixture
def mock_vm():
    return MockMainViewModel()

@pytest.fixture
def main_window(qapp, mock_vm):
    """
    가짜 VM을 주입받은 MainWindow 생성
    """
    window = MainWindow(mock_vm)
    return window

# ------------------------------------------------------------------
# 3. 테스트 케이스
# ------------------------------------------------------------------

def test_initial_ui_state(main_window, qtbot):
    """
    [기본] 창이 제대로 뜨고, 제목과 초기 상태가 맞는지 확인
    """
    # qtbot: 위젯을 등록하면 테스트 종료 시 안전하게 닫아줌
    qtbot.addWidget(main_window)
    
    # 1. 제목 확인
    assert main_window.windowTitle() == "KRISS Robot Polishing Machine"
    
    # 2. 상태바 위젯 존재 확인
    #    StatusIndicatorBox가 상태바에 잘 추가되었는지
    assert main_window.twincat_indicator is not None
    
    # 3. 초기 상태 확인 (Disconnected)
    #    (private 변수 접근: _title_text, _lbl_state 등)
    #    StatusIndicatorBox 내부 라벨 텍스트 확인
    state_label = main_window.twincat_indicator._lbl_state.text()
    assert state_label == "Disconnected"


def test_status_update_via_signal(main_window, mock_vm, qtbot):
    """
    [시나리오] VM에서 'twincat_status_data' 시그널을 보내면
            상태바의 위젯(StatusIndicatorBox)이 갱신되는지 확인
    """
    qtbot.addWidget(main_window)
    
    # --- Given ---
    # 보낼 데이터 준비
    new_data = {'title': 'TwinCAT', 'state': 'connected'}
    
    # --- When ---
    # 가짜 VM에서 시그널 발사!
    mock_vm.twincat_status_data.emit(new_data)
    
    # --- Then ---
    # 위젯의 텍스트가 'Connected'로 바뀌었는지 확인
    # (StatusIndicatorBox는 state의 첫 글자를 대문자로 바꿔서 표시함)
    actual_text = main_window.twincat_indicator._lbl_state.text()
    assert actual_text == "Connected"


def test_recovery_dialog_trigger(main_window, mock_vm, qtbot, mocker):
    """
    [시나리오] VM에서 'show_recovery_dialog' 시그널을 보내면
            재접속 UI(모달)가 뜨고 로직이 실행되는지 확인
    """
    qtbot.addWidget(main_window)
    main_window.show() # 모달 위치 계산을 위해 show 필요

    # 1. 모달 창(SplashScreen)이 실제로 뜨면 테스트가 멈추므로 Mocking
    #    ui.main_window 모듈 내부에서 import한 SplashScreen을 가짜로 교체
    MockSplash = mocker.patch('ui.main_window.SplashScreen')
    mock_splash_instance = MockSplash.return_value
    
    # 2. QMessageBox도 뜨면 안 되므로 Mocking
    mocker.patch('ui.main_window.QMessageBox')

    # --- When ---
    # 복구 요청 시그널 발사!
    mock_vm.show_recovery_dialog.emit()
    
    # --- Then ---
    # 1. 스플래시 화면이 생성되고 show() 되었는지 확인
    MockSplash.assert_called()
    mock_splash_instance.show.assert_called_once()
    
    # 2. VM의 retry_connection 메서드가 호출되었는지 확인
    #    (이때 인자로 UI 콜백 함수가 넘어갔는지까지 확인 가능)
    #    하지만 여기선 MockViewModel의 메서드 호출 여부는 직접 체크 어려우므로
    #    mock_vm을 MagicMock으로 감싸거나 로직 내 print로 확인.
    #    여기서는 스플래시 닫힘 여부로 간접 확인
    
    # 3. 로직 종료 후 스플래시가 닫혔는지 확인
    mock_splash_instance.close.assert_called_once()