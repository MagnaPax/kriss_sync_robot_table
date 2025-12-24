
import sys
import os
import pyads
import time
import unittest
from unittest.mock import MagicMock

# 프로젝트 루트를 경로에 추가 (tests/unit/ 기준 -> ../../)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from communication.servo_adapter import ServoAdapter
from communication.twincat_connector import TwinCATConnector
from models.servo_pose_key import ServoSignal

class TestRestoredLogic(unittest.TestCase):
    def setUp(self):
        # Mock Connector 및 핸들 설정
        self.mock_connector = MagicMock(spec=TwinCATConnector)
        self.mock_plc = MagicMock()
        self.mock_connector.handle = self.mock_plc
        self.adapter = ServoAdapter(self.mock_connector)

    def test_request_immediate_stop_propagates_exception(self):
        """
        [시나리오]
        ServoAdapter.request_immediate_stop() 실행 중 특정 축에서 에러가 발생하면
        내부에서 먹고 들어가는게 아니라, 밖으로(Caller에게) 예외를 던지는지 확인.
        이것이 '순수 모델'의 조건임.
        """
        
        # 1. 3번 축 정지 신호 인가 시 에러 발생 시뮬레이션
        def write_side_effect(name, value, plc_type):
            if "MAIN.bStop3" in name and value == True:
                raise pyads.ADSError(text="symbol not found", err_code=1808)
            return None

        self.mock_plc.write_by_name.side_effect = write_side_effect

        print("\n--- [Test] Emergency Stop Exception Propagation Start ---")
        
        # 2. 실행 및 검증
        # request_immediate_stop()을 호출했을 때 ADSError가 밖으로 튀어나와야 함
        with self.assertRaises(pyads.ADSError):
            self.adapter.request_immediate_stop()

        print("--- [Test] Exception correctly propagated to caller ---")

if __name__ == "__main__":
    unittest.main()
