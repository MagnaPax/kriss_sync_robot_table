# communication/turntable_adapter.py
import time
import pyads
from typing import TYPE_CHECKING, Union
from communication.twincat_connector import TwinCATConnector
from models.servo_pose_key import ServoPoseKey, ServoSignal
from models.servo_pose_model import ServoPose


# 타입 힌트용
if TYPE_CHECKING:
    from communication.mock_plc import MockConnection


class ServoAdapter:
    """
    Panasonic 서보 모터(총 3축) 통신 로직을 담당하는 Model 레이어
    
    [관리 대상]
    - Axis 1: Tool 공전 모터
    - Axis 2: Tool 자전 모터
    - Axis 3: 턴테이블 모터
    
    [역할]
    - FanucAdapter와 동일한 위상의 하드웨어 드라이버
    - LREAL(실수) 데이터를 쓰고 읽음
    """

    def __init__(self, connector: TwinCATConnector):
        self.connector = connector

    @property
    def _plc(self) -> Union[pyads.Connection, 'MockConnection']:
        """
        Connector의 활성 핸들을 가져오는 단축 속성

        사용 예:
            self._plc : TwinCATConnector.handle 실행돼서 _twincat(트윈캣 핸들) 반환됨
        """
        return self.connector.handle


    # ==========================================================================
    # 1. 기본 설정 및 안전 (Setup & Safety)
    # ==========================================================================
    def set_servo_state(self, axis_index: int, enable: bool):
        """
        [전원 제어] 특정 축의 서보 모터 전원(Servo ON) 및 읽기 기능을 켠다/끈다.
        
        Args:
            axis_index (int): 축 번호 (1, 2, 3)
            enable (bool): True(ON) / False(OFF)
        """
        plc = self._plc
        
        # 1. 서보 전원 (bServoOn)
        plc.write_by_name(ServoSignal.SERVO_ON.path(axis_index), enable, pyads.PLCTYPE_BOOL)
        
        # 2. 피드백 읽기 활성화 (bReadPos, bReadVel)
        #    원본 1219_Test.py의 Servo_Read_On 함수 로직 이식
        plc.write_by_name(ServoSignal.READ_POS_ON.path(axis_index), enable, pyads.PLCTYPE_BOOL)
        plc.write_by_name(ServoSignal.READ_VEL_ON.path(axis_index), enable, pyads.PLCTYPE_BOOL)

        # 신호 안정화 대기 (하드웨어 특성 고려)
        time.sleep(0.05)

        # 3. 짧은 대기 후 정지 신호 해제 (Pulse 방식인 경우 대비)
        #    Test 파일에서는 s키 누르면 0.5초간 Stop을 주는 로직이 있었음
        time.sleep(0.1)
        plc.write_by_name(ServoSignal.STOP.path(axis_index), False, pyads.PLCTYPE_BOOL)


    def clear_trigger(self, axis_index: int):
        """
        [트리거 초기화] 이동 신호(Rising Edge용)를 False로 내린다.
        """
        plc = self._plc
        plc.write_by_name(ServoSignal.MOVE_VEL.path(axis_index), False, pyads.PLCTYPE_BOOL)
        plc.write_by_name(ServoSignal.MOVE_ABS.path(axis_index), False, pyads.PLCTYPE_BOOL)


    # ==========================================================================
    # 2. 상태 모니터링 (Read Feedback)
    # ==========================================================================
    def is_busy(self, axis_index: int) -> bool:
        """
        [상태 확인] 해당 축이 현재 움직이고 있는가?
        PLC: MAIN.Busy{i}
        """
        try:
            return bool(self._plc.read_by_name(ServoSignal.BUSY.path(axis_index), pyads.PLCTYPE_BOOL))
        except Exception:
            return False


    def read_current_pose(self, axis_index: int) -> dict:
        """
        [피드백] 현재 위치와 속도를 읽어온다.
        PLC: MAIN.Act_pos{i}, MAIN.Act_vel{i}
        """
        try:
            curr_pos = self._plc.read_by_name(ServoSignal.ACT_POS.path(axis_index), pyads.PLCTYPE_LREAL)
            curr_vel = self._plc.read_by_name(ServoSignal.ACT_VEL.path(axis_index), pyads.PLCTYPE_LREAL)
            return {'position': curr_pos, 'velocity': curr_vel}
        except Exception:
            return {'position': 0.0, 'velocity': 0.0}
        

    # ==========================================================================
    # 3. 이동 명령 (Write Command)
    # ==========================================================================

    def move_velocity(self, axis_index: int, target_velocity: float):
        """
        [속도 제어 이동] Tool 공전/자전용 (Axis 1, 2)
        특징: 목표 위치 없이 '속도'만 주고 계속 회전함 (bMoveVel)
        
        Args:
            axis_index: 축 번호
            target_velocity: 목표 속도 (deg/s) - 이미 스케일링 된 값
        """
        plc = self._plc
        
        # 1. 속도 입력 (MAIN.vel{i})
        plc.write_by_name(ServoSignal.TARGET_VEL.path(axis_index), target_velocity, pyads.PLCTYPE_LREAL)
        
        # 2. 속도 제어 트리거 ON (MAIN.bMoveVel{i})
        #    Test1.py: plc.write_by_name('MAIN.bMoveVel1', True, ...)
        plc.write_by_name(ServoSignal.MOVE_VEL.path(axis_index), True, pyads.PLCTYPE_BOOL)


    def move_absolute(self, axis_index: int, target_pos: float, target_velocity: float):
        """
        [위치 제어 이동] 턴테이블용 (Axis 3)
        특징: 목표 '위치'로 이동 후 멈춤 (bMoveAbs)
        
        Args:
            axis_index: 축 번호
            target_pos: 목표 각도 (deg)
            target_velocity: 이동 속도 (deg/s)
        """
        plc = self._plc

        # 1. 목표 위치 입력 (MAIN.pos{i})
        plc.write_by_name(ServoSignal.TARGET_POS.path(axis_index), target_pos, pyads.PLCTYPE_LREAL)

        # 2. 이동 속도 입력 (MAIN.vel{i})
        plc.write_by_name(ServoSignal.TARGET_VEL.path(axis_index), target_velocity, pyads.PLCTYPE_LREAL)
        
        # 3. 절대 이동 트리거 (Pulse)
        #    Rising Edge(False -> True)를 만들어야 확실하게 동작함
        plc.write_by_name(ServoSignal.MOVE_ABS.path(axis_index), False, pyads.PLCTYPE_BOOL)
        time.sleep(0.01)
        plc.write_by_name(ServoSignal.MOVE_ABS.path(axis_index), True, pyads.PLCTYPE_BOOL)
