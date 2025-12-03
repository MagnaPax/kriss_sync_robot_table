# tests/unit/test_twincat_connector.py
import pytest
from unittest.mock import MagicMock
from communication.twincat_connector import TwinCATConnector
from core.settings import TwinCATConfig

"""
pytest tests/unit/test_twincat_connector.py
"""

# ------------------------------------------------------------------
# Fixture: 테스트용 커넥터 준비 (데모 모드 강제 설정)
# ------------------------------------------------------------------
@pytest.fixture
def demo_connector(mocker):
    """
    [수정됨] SETTINGS 객체 자체를 Patch하여 확실하게 데모 모드 적용
    """
    # 1. 조작된 Config 객체 생성
    mock_config = TwinCATConfig(
        ams_net_id='127.0.0.1.1.1',
        port=851,
        demo_mode=True  # [핵심] True로 설정
    )
    
    # 2. SETTINGS.twincat 속성이 호출되면 위 객체를 반환하도록 설정
    #    (PropertyMock을 사용하여 @property를 덮어씀)
    mocker.patch('core.settings.Settings.twincat', new_callable=mocker.PropertyMock, return_value=mock_config)
    
    # 3. 커넥터 생성 (이제 __init__에서 True를 읽어감)
    connector = TwinCATConnector()
    
    return connector

# ------------------------------------------------------------------
# 테스트 케이스
# ------------------------------------------------------------------

def test_initial_state(demo_connector):
    """초기 상태는 연결 끊김이어야 함"""
    assert demo_connector.is_connected is False
    
    # 연결 전에는 handle 접근 시 에러가 나야 함
    with pytest.raises(ConnectionError):
        _ = demo_connector.handle


def test_connect_success(demo_connector):
    """연결 시도 성공 테스트 (데모 모드)"""
    # When: 연결 시도
    demo_connector.connect()
    
    # Then: 연결 상태가 True여야 함
    assert demo_connector.is_connected is True
    
    # Then: 핸들(객체)을 가져올 수 있어야 함
    assert demo_connector.handle is not None


def test_disconnect_logic(demo_connector):
    """연결 해제 로직 테스트"""
    # Given: 연결된 상태
    demo_connector.connect()
    assert demo_connector.is_connected is True
    
    # When: 해제
    demo_connector.disconnect()
    
    # Then: 상태 변경 확인
    assert demo_connector.is_connected is False
    assert demo_connector._twincat is None


def test_heartbeat_check_success(demo_connector):
    """Heartbeat(Check Connection) 성공 테스트"""
    # Given: 연결됨
    demo_connector.connect()
    
    # When: 상태 체크
    is_alive = demo_connector.check_connection()
    
    # Then: 살아있어야 함
    assert is_alive is True


def test_heartbeat_check_failure(demo_connector, mocker):
    """
    [중요] 연결이 끊어졌을 때(예외 발생 시) 처리 테스트
    """
    # Given: 연결됨
    demo_connector.connect()
    
    # 1. 내부 연결 객체의 read_state 메서드가 에러를 뱉도록 조작 (선 뽑힘 시뮬레이션)
    #    (MockConnection이든 pyads.Connection이든 read_state 메서드가 있다고 가정)
    mocker.patch.object(demo_connector._twincat, 'read_state', side_effect=Exception("Lost Connection"))
    
    # When: 상태 체크
    is_alive = demo_connector.check_connection()
    
    # Then:
    # 1. 결과는 False여야 함
    assert is_alive is False
    # 2. 내부적으로 disconnect()가 호출되어 상태가 False로 변해야 함
    assert demo_connector.is_connected is False