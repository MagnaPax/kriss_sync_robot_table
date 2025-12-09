"""
tests/test_position_model.py
----------------------------
models/position_model.py 모듈의 공식 단위 테스트

테스트 항목:
1. Position 데이터 클래스의 to_dict() 메서드 검증
2. FANUCPoseModel.parse_positions_from_data()
    - 성공 케이스 (정상 데이터)
    - 실패 케이스: 입력이 dict가 아닐 때 (TypeError)
    - 실패 케이스: 내부 데이터가 dict가 아닐 때 (ValueError)
    - 실패 케이스: 빈 딕셔너리 입력 (ValueError)
    - 실패 케이스: 필수 키(예: 'x') 누락 (KeyError)
    - 실패 케이스: 좌표 값 타입 오류 (ValueError)
3. FANUCPoseModel.get_position()
    - 성공 케이스
    - 실패 케이스: 존재하지 않는 ID (KeyError)

실행 방법:
    (프로젝트 루트에서)
    pytest tests/test_position_model.py
"""

import sys
import pytest
from pathlib import Path
from typing import Dict, Any

# --- 경로 문제 해결 ---
# 프로젝트 루트 디렉토리를 sys.path에 추가하여 'models' 모듈을 찾을 수 있도록 함
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 테스트 대상 모듈 임포트
from models.fanuc_pose_model import FANUCPose, FANUCPoseModel

# =============================================================================
# Fixtures (테스트용 데이터)
# =============================================================================

@pytest.fixture
def sample_data() -> Dict[str, Any]:
    """[Happy Path] FANUCPoseModel의 main 테스트에서 가져온 정상 샘플 데이터"""
    return {
        "Macro_1": {
            "macro_id": "Macro_1", 
            "name": "매크로 1 이름", 
            "x": 100.1, "y": 200.2, "z": 0.0, 
            "w": 0.0, "p": 0.0, "r": 10.0
        },
        "Macro_2": {
            "macro_id": "Macro_2", 
            "name": "매크로 2 이름", 
            "x": 111.0, "y": 222.0, "z": 333.0, 
            "w": 44.0, "p": 55.0, "r": 66.0
        }
    }

@pytest.fixture
def parsed_positions(sample_data: Dict[str, Any]) -> Dict[str, Position]:
    """파싱이 완료된 Position 객체 딕셔너리 (get_position 테스트용)"""
    return FANUCPoseModel.parse_positions_from_data(sample_data)


# =============================================================================
# Test Cases
# =============================================================================

# --- 1. Position 데이터 클래스 테스트 ---

def test_position_to_dict():
    """Position 객체의 to_dict() 메서드가 정확한 dict를 반환하는지 테스트"""
    pos = Position(x=1.0, y=2.0, z=3.0, w=4.0, p=5.0, r=6.0)
    expected = {"x": 1.0, "y": 2.0, "z": 3.0, "w": 4.0, "p": 5.0, "r": 6.0}
    assert pos.to_dict() == expected

# --- 2. FANUCPoseModel.parse_positions_from_data() 테스트 ---

def test_parse_success(sample_data: Dict[str, Any]):
    """[성공] 정상적인 데이터 파싱을 테스트합니다."""
    positions = FANUCPoseModel.parse_positions_from_data(sample_data)
    
    assert isinstance(positions, dict)
    assert len(positions) == 2
    assert "Macro_1" in positions
    assert "Macro_2" in positions
    assert isinstance(positions["Macro_1"], Position)
    assert positions["Macro_1"].x == 100.1
    assert positions["Macro_2"].r == 66.0

def test_parse_fail_not_a_dict():
    """[실패] 입력 데이터가 dict가 아닐 때 TypeError를 발생시키는지 테스트"""
    invalid_data = ["Not", "a", "dict"]
    
    with pytest.raises(TypeError, match="dict 형식이어야 합니다"):
        FANUCPoseModel.parse_positions_from_data(invalid_data) # type: ignore

def test_parse_fail_inner_data_not_dict(sample_data: Dict[str, Any]):
    """[실패] 내부 매크로 데이터가 dict가 아닐 때 ValueError를 발생시키는지 테스트"""
    sample_data["Macro_Bad"] = "This is not a dict"
    
    with pytest.raises(ValueError, match="데이터가 dict가 아닙니다"):
        FANUCPoseModel.parse_positions_from_data(sample_data)

def test_parse_fail_empty_dict():
    """[실패] 빈 딕셔너리가 입력될 때 ValueError를 발생시키는지 테스트"""
    with pytest.raises(ValueError, match="로드된 매크로가 하나도 없습니다"):
        FANUCPoseModel.parse_positions_from_data({})

def test_parse_fail_missing_key():
    """[실패] 필수 좌표 키(예: 'x')가 누락되었을 때 KeyError를 발생시키는지 테스트"""
    invalid_data = {
        "Macro_Bad": { "y": 1.0, "z": 1.0, "w": 0, "p": 0, "r": 0 }
    }
    
    with pytest.raises(KeyError, match="필수 키 'x'가 없습니다"):
        FANUCPoseModel.parse_positions_from_data(invalid_data)

def test_parse_fail_bad_value_type():
    """[실패] 좌표 값이 숫자가 아닐 때 ValueError를 발생시키는지 테스트"""
    invalid_data = {
        "Macro_Bad": { "x": "NotANumber", "y": 1, "z": 1, "w": 0, "p": 0, "r": 0 }
    }
    
    with pytest.raises(ValueError, match="값이 숫자가 아닙니다"):
        FANUCPoseModel.parse_positions_from_data(invalid_data)

# --- 3. FANUCPoseModel.get_position() 테스트 ---

def test_get_position_success(parsed_positions: Dict[str, Position]):
    """[성공] 파싱된 딕셔너리에서 ID로 Position 객체를 가져오는지 테스트"""
    pos1 = FANUCPoseModel.get_position(parsed_positions, "Macro_1")
    assert isinstance(pos1, Position)
    assert pos1.x == 100.1

def test_get_position_fail_keyerror(parsed_positions: Dict[str, Position]):
    """[실패] 존재하지 않는 ID로 조회 시 KeyError를 발생시키는지 테스트"""
    with pytest.raises(KeyError, match="찾을 수 없습니다"):
        FANUCPoseModel.get_position(parsed_positions, "Macro_99")