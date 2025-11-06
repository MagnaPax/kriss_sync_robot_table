"""
tests/test_macro_settings_dialog.py
-----------------------------------
ui/dialogs/macro_settings_dialog.py 모듈 테스트

테스트 항목:
1. 다이얼로그 생성 및 위젯 초기화 검증
2. 사용자 입력 시뮬레이션 및 데이터 수집 검증
3. 'Save' 버튼 클릭 시 `save_json` 성공/실패 시나리오 검증
    - 성공: 올바른 데이터로 `save_json` 호출
    - 실패: `save_json`이 False 반환 시 `QMessageBox` 호출

실행 방법:
    pytest tests/test_macro_settings_dialog.py

    만약 tests 폴더 안의 모든 테스트 파일의 실행을 원한다면(pytest.ini 이용)
    pytest    
"""

import os
import sys
import pytest
from pathlib import Path

# --- 경로 문제 해결 ---
# test_logger.py와 동일한 방식
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# --- PyQt6 및 테스트 대상 임포트 ---
# pytest-qt를 사용하려면 QApplication이 필요합니다.
# (pytest-qt가 자동으로 'app' fixture를 제공하므로 직접 만들 필요 없음)
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton, QLineEdit, QDoubleSpinBox
from PyQt6.QtCore import Qt
from ui.dialogs.macro_settings_dialog import MacroSettingsDialog
from utils.logger import Logger # 로거 초기화 보장

# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def ensure_logger():
    """
    모든 테스트 전에 Logger가 한 번 초기화되도록 보장합니다.
    (file_handler.py가 로그를 기록할 수 있도록)
    """
    Logger()

@pytest.fixture
def dialog(qtbot, ensure_logger):
    """
    테스트할 MacroSettingsDialog 인스턴스를 생성하고 qtbot에 등록합니다.
    """
    test_dialog = MacroSettingsDialog()
    qtbot.addWidget(test_dialog) # qtbot이 테스트 종료 시 자동으로 dialog 파괴
    yield test_dialog
    # yield 이후 qtbot이 자동으로 위젯을 정리합니다.


# =============================================================================
# Test Cases
# =============================================================================

def test_dialog_initialization(dialog):
    """
    다이얼로그가 정상적으로 생성되고 위젯들이 초기화되었는지 검증
    
    검증:
        - 윈도우 타이틀이 'Macro Settings'인지 확인
        - macro_widgets 딕셔너리에 4개의 매크로가 모두 등록되었는지 확인
    """
    assert dialog.windowTitle() == "Macro Settings"
    
    # _init_ui에서 4개의 매크로 그룹이 생성되었는지 확인
    widget_keys = list(dialog.macro_widgets.keys())
    assert len(widget_keys) == 4
    assert "Macro_1" in widget_keys
    assert "Macro_2" in widget_keys
    assert "Macro_3" in widget_keys
    assert "Macro_4" in widget_keys
    
    # Macro_1의 'name_input' 위젯이 QLineEdit인지 확인
    assert isinstance(dialog.macro_widgets["Macro_1"]['name_input'], QLineEdit)


def test_gather_macro_data(dialog, qtbot):
    """
    사용자 입력을 시뮬레이션하고 _gather_macro_data 함수가
    데이터를 올바르게 수집하는지 테스트
    
    검증:
        - QLineEdit, QDoubleSpinBox에 값을 입력
        - _gather_macro_data 호출 시 해당 값이 딕셔너리로 반환됨
    """
    macro_id = "Macro_1"
    widgets = dialog.macro_widgets[macro_id]
    
    # qtbot을 사용하여 사용자 입력 시뮬레이션
    qtbot.keyClicks(widgets['name_input'], "Test Name")
    widgets['X'].setValue(123.456)
    widgets['Y'].setValue(-789.0)
    widgets['R'].setValue(90.0)
    
    # 데이터 수집 함수 직접 호출
    gathered_data = dialog._gather_macro_data(macro_id, widgets)
    
    # 결과 검증
    assert gathered_data['macro_id'] == "Macro_1"
    assert gathered_data['name'] == "Test Name"
    assert gathered_data['x'] == 123.456
    assert gathered_data['y'] == -789.0
    assert gathered_data['z'] == 0.0 # 기본값
    assert gathered_data['r'] == 90.0


def test_save_button_click_success(dialog, qtbot, monkeypatch, tmp_path):
    """
    'Save' 버튼 클릭 시 '성공' 시나리오 테스트
    
    검증:
        - load_json이 호출됨
        - save_json이 올바른 데이터와 경로로 호출됨
    """
    macro_id = "Macro_1"
    test_path = tmp_path / "test_macro_settings.json"
    
    # --- Mocking (가짜 함수/변수 설정) ---
    
    # 1. file_handler의 함수들을 mocking
    #    (실제 파일 시스템에 접근하지 않도록)
    
    # load_json은 항상 빈 딕셔너리를 반환하도록 설정
    mock_load = lambda path: {}
    monkeypatch.setattr("ui.dialogs.macro_settings_dialog.load_json", mock_load)
    
    # save_json은 호출된 인수(path, data)를 캡처하도록 설정
    class SaveCapture:
        called_with = None
        def mock_save(self, path, data):
            self.called_with = {"path": path, "data": data}
            return True # 저장 성공
            
    capture = SaveCapture()
    monkeypatch.setattr("ui.dialogs.macro_settings_dialog.save_json", capture.mock_save)

    # 2. CONFIG_MACRO_PATH가 임시 경로를 가리키도록 설정
    monkeypatch.setattr("ui.dialogs.macro_settings_dialog.CONFIG_MACRO_PATH", test_path)

    # --- 시뮬레이션 ---
    
    # 3. Macro_1 폼에 데이터 입력
    widgets = dialog.macro_widgets[macro_id]
    qtbot.keyClicks(widgets['name_input'], "Final Test")
    widgets['X'].setValue(1.1)
    
    # 4. Macro_1의 'Save' 버튼 클릭
    save_btn = widgets['save_btn']
    qtbot.mouseClick(save_btn, Qt.MouseButton.LeftButton)
    
    # --- 검증 ---
    
    # 5. save_json이 올바른 경로로 호출되었는지 확인
    assert capture.called_with is not None, "save_json이 호출되지 않았습니다."
    assert capture.called_with["path"] == test_path
    
    # 6. save_json이 올바른 데이터로 호출되었는지 확인
    saved_data = capture.called_with["data"]
    assert "Macro_1" in saved_data
    assert saved_data["Macro_1"]["name"] == "Final Test"
    assert saved_data["Macro_1"]["x"] == 1.1


def test_save_button_click_failure(dialog, qtbot, monkeypatch, tmp_path):
    """
    'Save' 버튼 클릭 시 '실패' 시나리오 테스트 (IOError)
    
    검증:
        - save_json이 False를 반환할 때
        - QMessageBox.critical이 호출됨
    """
    macro_id = "Macro_1"
    test_path = tmp_path / "locked_macro_settings.json"
    
    # --- Mocking ---
    
    # 1. load_json은 빈 값 반환
    monkeypatch.setattr("ui.dialogs.macro_settings_dialog.load_json", lambda path: {})
    
    # 2. save_json은 무조건 False (실패)를 반환
    monkeypatch.setattr("ui.dialogs.macro_settings_dialog.save_json", lambda path, data: False)
    
    # 3. CONFIG_MACRO_PATH 설정
    monkeypatch.setattr("ui.dialogs.macro_settings_dialog.CONFIG_MACRO_PATH", test_path)
    
    # 4. QMessageBox.critical이 호출되는지 캡처
    class MsgBoxCapture:
        called = False
        def mock_critical(self, *args):
            self.called = True
            
    msg_capture = MsgBoxCapture()
    monkeypatch.setattr(QMessageBox, "critical", msg_capture.mock_critical)
    
    # --- 시뮬레이션 ---
    
    # 5. Macro_1의 'Save' 버튼 클릭
    save_btn = dialog.macro_widgets[macro_id]['save_btn']
    qtbot.mouseClick(save_btn, Qt.MouseButton.LeftButton)

    # --- 검증 ---
    
    # 6. QMessageBox.critical이 호출되었는지 확인
    assert msg_capture.called is True, \
        "파일 저장 실패 시 QMessageBox.critical이 호출되어야 합니다."