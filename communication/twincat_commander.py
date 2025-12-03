# communication/twincat_commander.py
"""
TwinCAT Commander (Model Layer)
    원본파일(TxtFileReadFANUC.py)의 main 함수 로직

역할: FANUC 로봇 제어 로직 (좌표 전송, 시작/정지, 핸드셰이킹)
"""
import time
import pyads
from typing import Tuple, Optional, Union, TYPE_CHECKING

from communication.twincat_connector import TwinCATConnector
from communication.fanuc_utils import send_feed, send_coordinate



# 타입 검사기(Pylance)에게만 MockConnection의 존재를 알려줌
# 순환 참조(Circular Import) 오류를 방지하면서 타입 힌트를 제공하기 위해
if TYPE_CHECKING:
    from communication.mock_plc import MockConnection



class TwinCATCommander:
    """
    TwinCAT Commander (Model Layer)
    역할: FANUC 로봇 제어 로직 (좌표 전송, 시작/정지, 핸드셰이킹)
    """
    def __init__(self, connector: TwinCATConnector):
        self.connector = connector
        self._prev_coords: Optional[dict] = None

    @property
    def plc(self) -> Union[pyads.Connection, 'MockConnection']:
        """Connector의 활성 핸들을 가져오는 단축 속성"""
        return self.connector.handle
