# communication/twincat_commander.py
"""
TwinCAT Commander (Model Layer)
    전략 패턴(Strategy Pattern) 사용

    역할:
        TwinCAT 에 연결된 기기(FANUC 로봇, 턴테이블) 제어
"""
import time
import pyads
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Union, TYPE_CHECKING, Callable

from core.event_bus import EVENT_BUS
from communication.fanuc_adapter import FanucAdapter
from communication.twincat_connector import TwinCATConnector
from communication.turntable_adapter import TurntableAdapter
from communication.fanuc_utils import send_feed, send_coordinate, pause_process, resume_process


# 타입 검사기(Pylance)에게만 MockConnection의 존재를 알려줌
# 순환 참조(Circular Import) 오류를 방지하면서 타입 힌트를 제공하기 위해
if TYPE_CHECKING:
    from communication.mock_plc import MockConnection


# =========================================================
# 1. 추상 실행기 (Base Executor)
# =========================================================
class BaseExecutor(ABC):
    def __init__(self, robot: FanucAdapter, turntable: TurntableAdapter):
        self.robot = robot
        self.table = turntable

    @abstractmethod
    def can_execute(self, sample_data: dict) -> bool:
        """이 데이터 형식을 처리할 수 있는지 확인"""
        pass

    @abstractmethod
    def execute(self, sequence_data: list[dict]):
        """실제 실행 로직"""
        pass


# =========================================================
# 2. 전략 구현 (Strategies)
# =========================================================

class FanucOnlyExecutor(BaseExecutor):
    """로봇 단독 제어"""

    def can_execute(self, sample_data: dict) -> bool:
        # TXT 스키마의 키들이 포함되어 있는지 확인
        required_keys = {'tool_rotation_rpm', 'tool_revolution_rpm'} 
        return required_keys.issubset(sample_data.keys())

    def execute(self, sequence_data: list[dict]):
        # 기존 FanucAdapter 있던 루프 로직을 사용하거나 여기서 구현
        print("[Gateway] FANUC 단독 제어 모드로 실행합니다.")
        
        # (예시) 기존 FanucAdapter의 로직 위임
        # self.robot.run_legacy_sequence(sequence_data) 
        pass

class IntegratedExecutor(BaseExecutor):
    """
    CSV 파일 형식 (로봇 + 턴테이블 통합 제어)
    """
    def can_execute(self, sample_data: dict) -> bool:
        # CSV 스키마의 키들이 포함되어 있는지 확인
        required_keys = {'polar_coord_theta', 'polar_coord_radius'}
        return required_keys.issubset(sample_data.keys())

    def execute(self, sequence_data: list[dict]):
        print("[Gateway] 로봇+턴테이블 통합 제어 모드로 실행합니다.")
        
        # 1. 시작 신호
        self.robot.start_sequence_plc_signals()
        # self.table.start_signal()

        # 2. 통합 루프
        for row in sequence_data:
            # 동기화 및 전송 로직...
            pass
        
        # 3. 종료 신호
        self.robot.end_sequence_plc_signals()


class LegacyTXTEscutor(BaseExecutor):
    """
    레거시 TXT 파일 형식
    """



# =========================================================
# 3. 게이트웨이 (The Commander)
# =========================================================
class TwinCATCommander:

    """
    데이터 형식에 따라 적절한 Executor를 선택하여 실행하는 '게이트웨이'
    """
    def __init__(self, connector: TwinCATConnector):
        self.connector = connector
        
        # 하위 장치 컨트롤러
        self.robot = FanucAdapter(connector)
        self.turntable = TurntableAdapter(connector)

        # 등록된 실행기들 (우선순위 순서대로)
        self.executors: List[BaseExecutor] = [
            IntegratedExecutor(self.robot, self.turntable), # 더 구체적인 조건을 먼저 검사
            FanucOnlyExecutor(self.robot, self.turntable),  # 일반적인 조건
        ]


    def execute_batch_sequence(self, sequence_data: list[dict]):
        """
        [Gateway Logic]
        데이터의 첫 줄을 샘플로 채취하여 적절한 실행기를 찾는다.
        """
        if not sequence_data:
            return False, "데이터가 비어있습니다."

        sample_row = sequence_data[0]
        
        # 적절한 Executor 찾기
        target_executor = None
        for executor in self.executors:
            if executor.can_execute(sample_row):
                target_executor = executor
                break

        if target_executor:
            # 찾은 Executor에게 실행 위임
            return target_executor.execute(sequence_data)
        else:
            return False, "지원하지 않는 데이터 형식입니다."
