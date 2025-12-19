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
    # 1. 제어 신호 (Servo ON/OFF, 초기화)
    # ==========================================================================
    def set_initial_signals(self):
        """
        [시퀀스 시작 전 준비]
        서보 모터 전원을 켜고, 이동 트리거를 초기화한다
        """
        plc = self._plc

        # 1. 서보 온 (Servo ON) - 전원 공급
        # MAIN.bServoOn = True
        plc.write_by_name(ServoSignal.SERVO_ON.path, True, pyads.PLCTYPE_BOOL)

        # 2. 위치 읽기 활성화 (모니터링용)
        # MAIN.bReadPosOn = True
        plc.write_by_name(ServoSignal.READ_POS_ON.path, True, pyads.PLCTYPE_BOOL)
        
        # 3. 이동 신호 초기화 (Rising Edge 준비)
        # 이미 켜져 있을 수 있으므로 False로 내려둠
        # MAIN.bMoveAbsOn = False
        plc.write_by_name(ServoSignal.MOVE_START.path, False, pyads.PLCTYPE_BOOL)
        
        # 신호 안정화 대기
        time.sleep(0.1)

    def set_finish_signals(self):
        """[시퀀스 종료] 모터 전원을 끄거나 대기 상태로 전환"""
        plc = self._plc
        
        # 이동 신호 끄기
        plc.write_by_name(ServoSignal.MOVE_START.path, False, pyads.PLCTYPE_BOOL)
        
        # 서보 오프 (안전을 위해 전원 차단)
        # 필요에 따라 유지할 수도 있지만 안전상 끄는 것을 기본으로 함
        plc.write_by_name(ServoSignal.SERVO_ON.path, False, pyads.PLCTYPE_BOOL)

    def set_emergency_stop(self):
        """[비상 정지] 즉시 서보를 끈다"""
        # 턴테이블은 별도의 Stop 신호가 없으므로 Servo OFF로 대응
        self.set_finish_signals()



    # ==========================================================================
    # 2. 데이터 전송 (이동 명령)
    # ==========================================================================
    def move_to(self, angle: float, velocity: float):
        """
        [이동 명령 전송]
        목표 각도와 속도를 입력하고 이동 신호를 켠다
        
        Args:
            angle (float): 목표 각도 (deg)
            velocity (float): 회전 속도 (deg/s)
        """
        plc = self._plc

        # 1. 데이터 쓰기 (LREAL)
        # MAIN.position = angle
        plc.write_by_name(ServoPoseKey.ANGLE.plc_address, angle, pyads.PLCTYPE_LREAL)
        
        # MAIN.velocity = velocity
        plc.write_by_name(ServoPoseKey.VELOCITY.plc_address, velocity, pyads.PLCTYPE_LREAL)
        
        # 2. 이동 트리거 (Rising Edge 발생 필요)
        # 일단 False로 확실히 내렸다가 True로 올려야 PLC가 변화를 감지함
        # (Executor에서 제어할 수도 있지만, 편의상 여기서 Pulse를 만듦)
        plc.write_by_name(ServoSignal.MOVE_START.path, False, pyads.PLCTYPE_BOOL)
        time.sleep(0.01) 
        plc.write_by_name(ServoSignal.MOVE_START.path, True, pyads.PLCTYPE_BOOL)

    def reset_trigger(self):
        """
        [트리거 리셋]
        이동 완료 후 신호를 False로 되돌린다
        다음 이동 시 Rising Edge(False->True)를 만들기 위함
        """
        self._plc.write_by_name(ServoSignal.MOVE_START.path, False, pyads.PLCTYPE_BOOL)



    # ==========================================================================
    # 3. 상태 읽기 (피드백 듣기)
    # ==========================================================================

    def read_busy_signal(self) -> bool:
        """
        [Busy 신호 확인]
        MAIN.bMoveAbsBusy 확인

        Returns:
            True: 이동 중
            False: 대기 중 (이동 완료)
        """
        return bool(self._plc.read_by_name(ServoSignal.BUSY.path, pyads.PLCTYPE_BOOL))

    def read_current_angle(self) -> float:
        """
        [현재 위치 확인]
        MAIN.CurrentPos 읽기
        """
        return self._plc.read_by_name(ServoSignal.CURRENT_POS.path, pyads.PLCTYPE_LREAL)
    





    # ==========================================================================
    # TODO: 상태 읽기 (피드백 듣기)
    # ==========================================================================

    def read_current_status(self) -> ServoPose:
        """
        [피드백] 턴테이블의 현재 각도와 속도를 한 번에 읽어온다.
        """
        try:
            # 1. 현재 각도 (Position)
            # 변수명: MAIN.Turntable.CurrentPos (이미 정의된 ServoSignal 사용 권장)
            curr_pos = self._plc.read_by_name(ServoSignal.CURRENT_POS.path, pyads.PLCTYPE_LREAL)
            
            # 2. 현재 속도 (Velocity)
            # 변수명: MAIN.Turntable.CurrentVel (새로 정의하거나 문자열 직접 사용)
            # 예시: "MAIN.fActVelocity" 혹은 "MAIN.stAxisStatus.fActVelocity"
            curr_vel_path = "MAIN.Turntable.CurrentVel" 
            curr_vel = self._plc.read_by_name(curr_vel_path, pyads.PLCTYPE_LREAL)
            
            return ServoPose(angle=curr_pos, velocity=curr_vel)
            
        except Exception:
            return ServoPose(angle=0.0, velocity=0.0)