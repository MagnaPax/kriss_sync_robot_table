# communication/twincat_commander.py
"""
TwinCAT Commander (Model Layer)
    원본파일(TxtFileReadFANUC.py)의 main 함수 로직

역할: FANUC 로봇 제어 로직 (좌표 전송, 시작/정지, 핸드셰이킹)
"""
import time
import pyads
from typing import Tuple, Optional

from communication.twincat_connector import TwinCATConnector
from communication.fanuc_utils import send_feed, send_coordinate, pulse_signal



class TwinCATCommander:
    """
    Docstring for TwinCATCommander
    """