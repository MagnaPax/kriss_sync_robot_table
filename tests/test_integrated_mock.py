
import sys
import os
import unittest
import time
import threading
from unittest.mock import MagicMock

# 프로젝트 루트 경로 추가 (모듈 import를 위해)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from communication.twincat_commander import TwinCATCommander
from communication.mock_plc import MockConnection
from core.settings import AppConfig
from PyQt6.QtCore import QCoreApplication

print("Test Script Loaded...") # Debug print

class TestIntegratedExecutorWithMock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # QCoreApplication이 없으면 생성 (싱글톤)
        if not QCoreApplication.instance():
            cls.app = QCoreApplication(sys.argv)

    def setUp(self):
        # 1. Mock Setting
        from pathlib import Path
        self.config = AppConfig(
            name="TestApp", 
            version="1.0", 
            debug=True, 
            log_dir=Path("./logs")
        )
        
        # Mock Connection 생성
        self.mock_connection = MockConnection("127.0.0.1.1.1", 851)
        
        # 어댑터 생성 (Connector.handle 이 MockConnection을 반환하도록 설정)
        mock_connector = MagicMock()
        mock_connector.handle = self.mock_connection
        
        from communication.fanuc_adapter import FanucAdapter
        from communication.servo_adapter import ServoAdapter
        
        self.fanuc_adapter = FanucAdapter(connector=mock_connector)
        self.servo_adapter = ServoAdapter(connector=mock_connector)
        
        # Commander 생성 (Adapter 주입)
        self.commander = TwinCATCommander(self.config, self.fanuc_adapter, self.servo_adapter)
        
        # 2. 통합 실행기(IntegratedExecutor) 찾기
        from communication.twincat_commander import IntegratedExecutor
        self.executor = None
        for ex in self.commander.executors:
            if isinstance(ex, IntegratedExecutor):
                self.executor = ex
                break
        
        if not self.executor:
            raise RuntimeError("IntegratedExecutor를 찾을 수 없습니다.")

        # Mock Open
        self.mock_connection.open()
        
        # 더미 데이터 (신규 리팩토링된 키 이름 적용)
        self.test_data = [
            # 1번 시퀀스
            {
                'id': 1, 'PRLINE': 1,
                'x': 500.0, 'y': 0.0, 'z': 300.0, 'w': 180.0, 'p': 0.0, 'r': 0.0, # Robot
                'turntable_target_position': 45.0,  # tt_angle_tgt
                'turntable_moving_velocity': 20.0,  # tt_speed_tgt
                'spindle_rotation_velocity': 0.0,   # tool_rot
                'spindle_revolution_velocity': 60.0 # tool_rev
            },
            # 2번 시퀀스
            {
                'id': 2, 'PRLINE': 2,
                'x': 550.0, 'y': 0.0, 'z': 350.0, 'w': 180.0, 'p': 0.0, 'r': 0.0,
                'turntable_target_position': 90.0,
                'turntable_moving_velocity': 20.0,
                'spindle_rotation_velocity': 0.0,
                'spindle_revolution_velocity': 60.0
            }
        ]
        
    def tearDown(self):
        if self.mock_connection:
            self.mock_connection.close()

    def test_integrated_execution_flow(self):
        """
        IntegratedExecutor가 리팩토링된 네이밍 규칙 하에서도 
        정상적으로 동기화 핸드셰이크를 수행하는지 테스트
        """
        print("\n=== [TEST] Integrated Executor (Refactored) Start ===")
        
        from core.event_bus import EVENT_BUS
        EVENT_BUS.data.progress_updated = MagicMock()
        EVENT_BUS.log.message = MagicMock()
        
        # 실행
        success, msg = self.executor.execute(self.test_data)
        
        print(f"=== [TEST] Result: {success}, {msg} ===")
        
        self.assertTrue(success, f"Execution failed: {msg}")
        # 2 steps * progress update (processed) 가 최소 2번 호출되어야 함.
        self.assertGreaterEqual(EVENT_BUS.data.progress_updated.emit.call_count, 2)
        
if __name__ == '__main__':
    unittest.main()
