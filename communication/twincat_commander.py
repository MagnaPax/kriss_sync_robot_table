# communication/twincat_commander.py
"""
TwinCAT Commander (Model Layer)
    원본파일(TxtFileReadFANUC.py)의 main 함수 로직

역할: FANUC 로봇 제어 로직 (좌표 전송, 시작/정지, 핸드셰이킹)
"""
import time
import pyads
from typing import Tuple, Optional, Union, TYPE_CHECKING, Callable

from communication.twincat_connector import TwinCATConnector
from communication.fanuc_utils import send_feed, send_coordinate, pause_process, resume_process



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



    """
    TxtFileReadFANUC 로직 그대로

        변경 사항: 
            plc -> self.plc
            로그 처리
            리턴값 추가
    """
    def start_process(self) -> Tuple[bool, str]:
        # RSR신호 Pulse
        print("TP Program Start")
        self.plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', True, pyads.PLCTYPE_BOOL)   # MAIN.Robot1._UI1.UI09_RSR1 = RSR0001 / MAIN.Robot1._UI1.UI10_RSR2 = RSR0002
        time.sleep(0.05)

        # Loop신호(ON이면 루프 반복, OFF이면 루프 종료)
        self.plc.write_by_name('MAIN.Robot1._UI1.DI181', True, pyads.PLCTYPE_BOOL)

        self._prev_coords = None
        return True, "시작 신호 전송"
    
    def stop_process(self) -> Tuple[bool, str]:
        # Sequence 종료 시 루프 신호 OFF 
        self.plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', False, pyads.PLCTYPE_BOOL)
        self.plc.write_by_name('MAIN.Robot1._UI1.DI181', False, pyads.PLCTYPE_BOOL)

        return True, "정지 신호 전송"


    def pause_process(self):
        # fanuc_utils의 함수에 연결 객체(self.plc)를 넘겨줌
        pause_process(self.plc)

    def resume_process(self):
        resume_process(self.plc)


    # ======================================================
    def write_move_command(self, coords, previous_coords, init_done, i, lines, check_stop: Optional[Callable[[], bool]] = None) -> Tuple[dict, bool]:
        """
        단일 좌표 이동 명령
        
        Args:
            plc:               TwinCAT 연결 객체
            coords:            현재 스텝에서 이동할 목표 좌표 (F, X, Y, Z, W, P, R)
            previous_coords:   직전 스텝의 좌표 (Delta 계산용)
            init_done:         첫 번째 이동 명령이 수행되었는지 여부 (True/False)
            i:                 현재 처리 중인 라인 번호 (로그 출력용)
            lines:             전체 시퀀스 데이터 리스트 (전체 진행률 표시용)
            check_stop (Callable): 중단 요청이 있는지 확인하는 함수 (True면 중단)
        """
        
        # 1. Delta 계산
        if previous_coords is None:
            deltas = coords.copy()
        else:
            deltas = {key: coords[key] - previous_coords[key] for key in coords.keys()}
        
        previous_coords = coords

        # 2. 대기 및 전송 루프
        while True:
            # [수정] msvcrt 대신 외부에서 주입된 중단 체크 함수 사용
            if check_stop and check_stop():
                raise InterruptedError("사용자에 의해 중단됨")

            # [로직] 첫 줄이거나(init_done=False) OR 로봇이 요청(DO45=True)하면 전송
            if (not init_done) or self.plc.read_by_name('MAIN.Robot1._UO1.DO45', pyads.PLCTYPE_BOOL):
                
                # (로그 출력 생략...)

                # 데이터 전송
                send_feed(self.plc, coords['F'])
                send_coordinate(self.plc, deltas['X'], "X")
                send_coordinate(self.plc, deltas['Y'], "Y")
                send_coordinate(self.plc, deltas['Z'], "Z")
                send_coordinate(self.plc, deltas['W'], "W")
                send_coordinate(self.plc, deltas['P'], "P")
                send_coordinate(self.plc, deltas['R'], "R")

                init_done = True
                break
            
            else:
                # 신호 대기 (Polling)
                time.sleep(0.005)
        
        return previous_coords, init_done
