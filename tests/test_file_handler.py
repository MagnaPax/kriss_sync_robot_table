"""
tests/test_file_handler.py
--------------------------
utils/file_handler.py 모듈 테스트

테스트 항목:
1. 파일 저장 및 로드 성공 (Success case)
2. 존재하지 않는 파일 로드 (Fail case 1 -
   FileNotFound)
3. 형식이 깨진 JSON 파일 로드 (Fail case 2 - JSONDecodeError)
4. 파일 저장 시 IO 에러 발생 (Fail case 3 - IOError)
5. 로드 시 IO 에러 발생 (Fail case 4 - Race condition)

실행 방법:
    pytest tests/test_file_handler.py

    만약 tests 폴더 안의 모든 테스트 파일의 실행을 원한다면(pytest.ini 이용)
    pytest
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
import builtins

import pytest

# --- 경로 문제 해결 ---
# test_logger.py와 동일한 방식
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 테스트 대상 모듈
from utils.file_handler import save_json, load_json
from utils.logger import Logger # Logger를 임포트하여 로거가 초기화되도록 보장

# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def logger_paths():
    """
    Logger를 초기화하고 로그 파일 경로를 반환.
    module 스코프로 모든 테스트 실행 전 딱 한 번만 실행됩니다.
    
    file_handler.py가 로그를 쓰기 전에
    Logger가 먼저 초기화되는 것을 보장합니다.
    """
    logger_obj = Logger()
    return {
        "app_log": Path(logger_obj.LOG_FILE),
        "error_log": Path(logger_obj.ERROR_LOG_FILE)
    }

@pytest.fixture
def sample_data():
    """테스트용 샘플 딕셔너리 데이터 반환"""
    return {"macro_1": {"name": "Test", "x": 1.23}, "macro_2": "data"}


# =============================================================================
# Test Cases
# =============================================================================

### 1. 성공 케이스 (Happy Path) ###

def test_save_and_load_json_success(tmp_path, sample_data):
    """
    JSON 파일 저장 및 로드가 정상적으로 동작하는지 테스트
    
    검증:
        - save_json이 True를 반환
        - load_json이 원본 데이터를 반환
    """
    # tmp_path: pytest가 제공하는 임시 테스트 디렉토리
    test_file = tmp_path / "settings.json"
    
    # 1. 저장 테스트
    result_save = save_json(test_file, sample_data)
    assert result_save is True, "save_json이 True를 반환해야 합니다."
    assert test_file.exists(), "JSON 파일이 생성되지 않았습니다."
    
    # 2. 로드 테스트
    loaded_data = load_json(test_file)
    assert loaded_data == sample_data, "로드된 데이터가 원본과 다릅니다."

    
### 2. 실패 케이스: 파일 없음 (load) ###

def test_load_json_file_not_found(logger_paths):
    """
    존재하지 않는 파일 로드 시 None을 반환하는지 테스트
    
    검증:
        - load_json이 None을 반환
        - 이 경우는 '실패'가 아니므로 에러 로그를 기록하지 않음
    """
    non_existent_file = Path("non/existent/path/file.json")
    
    result = load_json(non_existent_file)
    assert result is None, "존재하지 않는 파일 로드 시 None을 반환해야 합니다."
    
    # test_logger.py의 파일 읽기 패턴 사용
    # 이 경우는 의도된 동작이므로 로그가 *없어야* 함
    time.sleep(0.3) # 로그 파일 동기화 대기 (test_logger.py 패턴)
    error_log_path = logger_paths["error_log"]
    content = error_log_path.read_text(encoding="utf-8")
    
    assert f"JSON 읽기 실패: {non_existent_file}" not in content, \
        "파일이 없을 때(os.path.exists)는 로그를 남기지 않아야 합니다."


### 3. 실패 케이스: 형식이 깨진 파일 (load) ###

def test_load_json_failure_invalid_json(tmp_path, logger_paths):
    """
    JSON 형식이 깨진 파일 로드 시 실패 테스트
    
    검증:
        - load_json이 None을 반환
        - 'JSON 읽기 실패' 경고 로그가 기록됨
    """
    test_file = tmp_path / "invalid.json"
    test_file.write_text("{'key': 'value', invalid_json:}") # 고의로 깨진 JSON
    
    result = load_json(test_file)
    assert result is None, "잘못된 JSON 로드 시 None을 반환해야 합니다."

    # test_logger.py의 파일 읽기 패턴 사용
    time.sleep(0.3) # 로그 파일 동기화 대기
    error_log_path = logger_paths["error_log"]
    content = error_log_path.read_text(encoding="utf-8")

    assert "JSON 읽기 실패" in content, "로그에 'JSON 읽기 실패' 메시지가 없습니다."
    assert str(test_file) in content, "로그에 파일 경로가 포함되어야 합니다."
    assert "Expecting property name" in content, "로그에 'JSONDecodeError'의 실제 메시지가 포함되어야 합니다."

### 4. 실패 케이스: 저장 권한 없음 (save) ###

def test_save_json_failure_io_error(tmp_path, sample_data, logger_paths, monkeypatch):
    """
    파일 저장 시 (IOError) 실패 테스트
    
    검증:
        - save_json이 False를 반환
        - 'JSON 저장 실패' 경고 로그가 기록됨
    """
    test_file = tmp_path / "locked_file.json"

    # --- 강제로 오류 발생시키기 ---
    # test_logger.py에서 monkeypatch를 사용한 것과 동일
    # 'builtins.open' 함수를 강제로 IOError를 발생시키는 함수로 교체
    def mock_open(*args, **kwargs):
        raise IOError("Permission denied")

    monkeypatch.setattr("builtins.open", mock_open)
    
    # 1. 저장 실행
    result = save_json(test_file, sample_data)
    
    # 2. 반환값 검증
    assert result is False, "IOError 발생 시 False를 반환해야 합니다."
    
    # 3. 로그 검증 (test_logger.py 패턴)
    time.sleep(0.3) # 로그 파일 동기화 대기
    error_log_path = logger_paths["error_log"]
    content = error_log_path.read_text(encoding="utf-8")
    
    assert "JSON 저장 실패" in content, "로그에 'JSON 저장 실패' 메시지가 없습니다."
    assert str(test_file) in content, "로그에 파일 경로가 포함되어야 합니다."
    assert "Permission denied" in content, "로그에 원본 에러 메시지가 포함되어야 합니다."


### 5. 실패 케이스: 읽기 중 파일 사라짐 (load) ###

def test_load_json_failure_race_condition(tmp_path, logger_paths, monkeypatch):
    """
    os.path.exists()는 통과했지만, 직후 open() 시
    파일이 사라지는 경우(Race condition) 테스트
    
    검증:
        - load_json이 None을 반환
        - 'JSON 읽기 실패' (FileNotFoundError) 로그가 기록됨
    """
    test_file = tmp_path / "race_condition.json"
    test_file.write_text("{}", encoding="utf-8") # 파일이 존재함
    
    # 1. 원본 open 함수를 먼저 변수에 저장
    original_open = builtins.open

    # --- 강제로 오류 발생시키기 ---
    # 'builtins.open'을 FileNotFoundError를 발생시키는 함수로 교체
    # 2. 'mock_open' 함수를 테스트 함수 내부에 정의
    def mock_open(*args, **kwargs):
        # 'r' 모드일 때만 에러 발생 (save 테스트에 영향 주지 않기 위함)
        # load_json()는 'r'로 호출
        if len(args) > 1 and args[1] == 'r':
            raise FileNotFoundError("File gone (race condition)")
        # 'r' 모드가 아니면(e.g., 'w'), 위에서 저장해둔 원본 함수를 호출
        return original_open(*args, **kwargs)
    
    # 3. 'builtins.open'을 새로 정의한 mock_open으로 교체
    monkeypatch.setattr("builtins.open", mock_open)

   # 1. 로드 실행
    result = load_json(test_file)
    
    # 2. 반환값 검증
    assert result is None, "FileNotFoundError 발생 시 None을 반환해야 합니다."
    
    # 3. 로그 검증 (test_logger.py 패턴)
    time.sleep(0.3) # 로그 파일 동기화 대기
    error_log_path = logger_paths["error_log"]
    content = error_log_path.read_text(encoding="utf-8")
    
    assert "JSON 읽기 실패" in content, "로그에 'JSON 읽기 실패' 메시지가 없습니다."
    assert "File gone (race condition)" in content, "로그에 원본 에러가 없습니다."
    # assert "FileNotFoundError" in content, "로그에 'FileNotFoundError'가 포함되어야 합니다."