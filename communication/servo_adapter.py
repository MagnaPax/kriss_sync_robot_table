# communication/turntable_adapter.py
import time
import pyads
import ctypes
from typing import TYPE_CHECKING, Union, Dict, Any, Callable, List
from communication.twincat_connector import TwinCATConnector
from models.servo_pose_key import ServoSignal
from models.servo_pose_key import ServoAxis, ST_PathData, Array500
from core.exceptions import ServoBusyError, ServoFaultError
from utils.logger import get_logger

logger = get_logger(__name__)



# 타입 힌트용
if TYPE_CHECKING:
    from communication.mock_plc import MockConnection


class ServoAdapter:
    """
    Panasonic 서보 모터(3축) 통신 로직을 담당하는 하위 장치 어댑터(Model Layer).
    
    이 클래스는 ServoAxis Enum에 정의된 물리적 축 정보를 바탕으로 TwinCAT PLC와 직접 통신하며
    각 축의 특성(Velocity/Position Mode)에 따른 이동 제어 및 상태 피드백을 제공한다

    [축 구성 및 제어 모드]
        - TOOL_REVOLUTION (Axis 1): 툴 공전 모터 (Velocity Mode - RPM 제어)
        - TOOL_ROTATION   (Axis 2): 툴 자전 모터 (Velocity Mode - RPM 제어)
        - TURNTABLE       (Axis 3): 턴테이블 모터 (Position Mode - 각도 + 속도 제어)

    [주요 역할]
        - 전원 및 읽기 신호 활성화 (Servo ON / Feedback Read)
        - 이동 명령 (Velocity Move / Absolute Position Move)
        - 안전 제어 (Stop, Error Clear, 원점 복귀)
        - 상태 모니터링 (Busy 확인, 속도 기반 움직임 감지, 에러 체크)
    """

    def __init__(self, connector: TwinCATConnector):
        self.connector = connector

        # 모든 축 이름을 미리 매핑해 둠 (캐싱)
        self._axis_names = {axis.value: axis.name for axis in ServoAxis}

    @property
    def _plc(self) -> Union[pyads.Connection, 'MockConnection']:
        """
        Connector의 활성 핸들을 가져오는 단축 속성

        사용 예:
            self._plc : TwinCATConnector.handle 실행돼서 _twincat(트윈캣 핸들) 반환됨
        """
        return self.connector.handle



    # ==========================================================================
    # 기본 설정 및 안전 (Setup & Safety)
    # ==========================================================================
    def set_servo_state(self, axis_index: int, enable: bool):
        """
        [전원 제어] 특정 축의 서보 모터 전원(Servo ON) 및 읽기 기능을 켠다/끈다.
        [원본] 131: def set_servo_power(self, enabled=True)
        [원본] 378: motor.set_servo_power(True)
        
        Args:
            axis_index (int): 축 번호 (1, 2, 3)
            enable (bool): True(ON) / False(OFF)
        """
        plc = self._plc
        
        # 1. 서보 전원 (bServoOn)
        plc.write_by_name(ServoSignal.SERVO_ON.get_plc_path(axis_index), enable, pyads.PLCTYPE_BOOL)
        
        if enable:
            # 2. 피드백 읽기 활성화 (Deprecated in new PLC logic)
            #    PLC에서 항상 읽기가 활성화되어 있으므로 별도 신호 전송 필요 없음
            pass

        # 신호 안정화 대기 (하드웨어 특성 고려)
        time.sleep(0.05)

    def turn_on_all_servos(self):
        """모든 서보모터의 전원을 켠다."""
        plc = self._plc

        # 1. 서보 전원 (bServoOn) - 3축 동시 켜기
        plc.write_list_by_name({
            ServoSignal.SERVO_ON.get_plc_path(ServoAxis.TOOL_REVOLUTION): True,
            ServoSignal.SERVO_ON.get_plc_path(ServoAxis.TOOL_ROTATION): True,
            ServoSignal.SERVO_ON.get_plc_path(ServoAxis.TURNTABLE): True
        })

        # 2. 안정화 대기
        time.sleep(0.5)
        logger.info("[Motor] 모든 서보 전원 ON 완료")

    def clear_error_pulse(self, axis_index: int) -> bool:
        """
        [에러 초기화] bReset 신호를 발생시켜 축의 에러 상태를 해제한다
            bReset=True 후 다시 False로 초기화 필수
        """
        plc = self._plc

        # 에러 초기화 전 서보 전원(Servo ON) 확인 및 활성화
        if not self.is_servo_on(axis_index):
            self.set_servo_state(axis_index, True)
            time.sleep(0.2) # 전원 투입 후 하드웨어 안정화 대기

        # 1. 에러 상태가 아니면 리셋 절차를 수행할 필요가 없음
        if not self.has_servo_error(axis_index): return True

        # 2. 리셋 명령 - bReset: False -> Wait -> True(Rising Edge: 리셋명령실행) -> Wait -> False
        plc.write_by_name(ServoSignal.ERROR_RESET.get_plc_path(axis_index), False, pyads.PLCTYPE_BOOL)  # False
        time.sleep(0.5)
        plc.write_by_name(ServoSignal.ERROR_RESET.get_plc_path(axis_index), True, pyads.PLCTYPE_BOOL)   # True
        time.sleep(0.5)
        plc.write_by_name(ServoSignal.ERROR_RESET.get_plc_path(axis_index), False, pyads.PLCTYPE_BOOL)  # False
        
        # 3. 실제로 에러가 해제되었는지 확인
        time.sleep(0.5)
        is_cleared = not self.has_servo_error(axis_index)
        return is_cleared

    def home_all_safely(self, timeout: float = 30.0) -> bool:
        """
        [원점 복귀] 모든 서보 축을 안전하게 초기화한다.
        
        절차:
            1. 안전을 위해 먼저 모든 축을 강제 정지한다.
            2. ServoAxis에 정의된 모든 축에 대해 원점 복귀(Homing) 신호를 전송한다.
            3. '물리적' 축이 이동을 마칠 때까지 대기한다.
        
        Args:
            timeout (float): 원점 복귀 최대 대기 시간 (기본 30초)
            
        Returns:
            bool: 모든 과정이 에러 없이 완료되면 True
        """
        # 1. 선행 조치: 현재 동작 중단
        self.request_immediate_stop()
        time.sleep(0.5) # 정지 후 안정화 대기

        # 2. 모든 축에 원점 복귀 명령 전송 (bHome False -> True)
        for axis in ServoAxis:
            self._homing(axis)
        
        # 명령이 반영되어 물리적 이동이 시작될 때까지 잠시 대기
        time.sleep(0.5)

        # 3. 정지 완료 대기
        start_time = time.time()
        while time.time() - start_time < timeout:
            # 모든 축 중 하나라도 움직이고 있는지 '물리적'으로 체크
            is_any_moving = any(self.is_servo_moving_physically(axis) for axis in ServoAxis)
            
            if not is_any_moving:
                return True
            
            # 아직 움직이는 중...
            time.sleep(0.2)

        # 4. 타임아웃 발생 시
        self.request_immediate_stop() # 안전을 위해 다시 정지 시도
        raise TimeoutError(f"원점 복귀 시간 초과 ({timeout}s)")

    def validate_axis_ready(self, axis_index: int, allow_busy: bool = False):
        """
        [이동 전 검증]
        문제가 있으면 예외(Exception)를 던진다.
        문제가 없으면 아무것도 반환하지 않는다 (None).
        
        Args:
            axis_index: 검증할 축 번호
            allow_busy: True면 Busy 상태여도 에러를 내지 않음 (속도 갱신 등)
        """
        axis_name = self._axis_names.get(int(axis_index), f"Axis{axis_index}")

        # 1. Busy 체크
        if not allow_busy and self.is_servo_logic_busy(axis_index):
            # 로그 대신 에러를 던져서 호출자가 알게 함
            raise ServoBusyError(f"[{axis_name}] 축이 현재 명령 처리 중(Busy)입니다.")

        # 2. Error 체크
        error_info = self._get_servo_error_info(axis_index)
        if error_info['active']:
            # 상세 정보를 담아서 에러를 던짐
            raise ServoFaultError(
                axis_name, 
                error_info['id'], 
                error_info['message']
            )


    # ==========================================================================
    # 안전 정지 (Stop & Safety)
    # ==========================================================================
    def _set_axis_stop_signals(self, axis: ServoAxis, active: bool):
        """내부용: 특정 축의 정지 관련 신호(Move 해제 및 Stop 신호)를 일괄 설정"""
        plc = self._plc
        if active:
            # 이동 신호 해제 (Latch 풀기)
            if axis in [ServoAxis.TOOL_REVOLUTION, ServoAxis.TOOL_ROTATION]:
                plc.write_by_name(ServoSignal.MOVE_VEL.get_plc_path(axis), False, pyads.PLCTYPE_BOOL)
            elif axis == ServoAxis.TURNTABLE:
                plc.write_by_name(ServoSignal.MOVE_ABS.get_plc_path(axis), False, pyads.PLCTYPE_BOOL)
        
        # 정지 신호 설정 (True: 정지 신호 인가 / False: 정지 신호 해제)
        # [원본] 160~162: MAIN.bStop1~3 Control
        plc.write_by_name(ServoSignal.STOP.get_plc_path(axis), active, pyads.PLCTYPE_BOOL)

    def stop_axis(self, axis: ServoAxis):
        """[개별 정지] 특정 축을 안전하게 정지시킨다."""
        self._set_axis_stop_signals(axis, True)     # 정지 신호 인가
        time.sleep(0.5)                             # 원본 코드 0.5초 준수
        self._set_axis_stop_signals(axis, False)    # 정지 신호 해제

    def request_immediate_stop(self):
        """모든 축에 정지 명령 내림"""
        errors = []

        # (A) 모든 축 이동 해제 & 정지 신호 ON
        for axis in ServoAxis:
            try:
                self._set_axis_stop_signals(axis, True)
            except Exception as e:
                # 실패하면 로그 모아두고 다음 축 정지 명령 시도
                errors.append(f"Axis {axis.name} 정지 명령 실패: {e}")

        # (B) 물리적 감속을 위한 공통 대기 (원본 코드 0.5초 준수)
        time.sleep(0.5)

        # (C) 정지 신호 해제 (다음 동작이 가능하도록 Reset)
        for axis in ServoAxis:
            try:
                self._set_axis_stop_signals(axis, False)
            except Exception as e:
                errors.append(f"Axis {axis.name} 정지 해제 실패: {e}")

        # 멈추지 않은 축이 있다면 예외를 던짐
        if errors:
            raise Exception(f"정지하지 않은 축이 있습니다: {', '.join(errors)}")

    def shutdown_all_with_power_off(self, timeout: float = 3.0):
        """정지 확인 후 전원까지 차단"""
        try:
            # 1. 정지 명령 내림
            self.request_immediate_stop()

            # 2. 모든 축의 속도가 임계값 이하로 떨어질 때까지 대기
            start_time = time.time()
            while time.time() - start_time < timeout:
                # 모든 축이 속도 임계값(is_servo_moving_physically) 이하인지 체크
                if not any(self.is_servo_moving_physically(axis) for axis in ServoAxis):
                    break
                time.sleep(0.1)

            # 3. 모든 축 서보 전원 차단
            for axis in ServoAxis:
                self.set_servo_state(axis, False)
            return True

        except Exception:
            return False

    def turn_off_all_servos(self):
        """
        [비상 정지] 모든 서보 전원 즉시 차단
        """
        try:
            for axis in ServoAxis:
                # 서보 전원 (bServoOn) 종료
                self.set_servo_state(axis.value, False)
        except Exception as e:
            # 비상 정지 중 에러는 로깅만 하고 무시 (최대한 끄는 게 중요)
            logger.error(f"Error during turn_off_all: {e}")



    # ==========================================================================
    # 알림 (Notification)
    # ==========================================================================
    def register_turntable_motion_done_callback(self, callback: Callable[[Any, Any], None]) -> int:
        """
        [Sync Step 4: Turntable Motion Done] 턴테이블 이동 완료(bDone3) 신호 감지
        
        '1년 뒤의 나'를 위한 설명:
            핸드셰이킹의 한 축을 담당하는 턴테이블의 완료 신호를 감지한다.
            DO46(로봇 완료)과 bDone3(턴테이블 완료)가 모두 True여야 다음 스텝으로 진행 가능.
        """
        # MAIN.bDone3 감시 (값이 변할 때마다 콜백)
        attr = pyads.NotificationAttrib(ctypes.sizeof(pyads.PLCTYPE_BOOL))
        attr.nTransMode = pyads.ADSTRANS_SERVERONCHA # type: ignore
        attr.nCycleTime = 100000 # type: ignore
        attr.nMaxDelay = 0 # type: ignore
        
        # 주소: MAIN.bDone3 (ServoSignal.DONE + Axis 3)
        symbol = ServoSignal.DONE.get_plc_path(ServoAxis.TURNTABLE.value)
        
        # add_device_notification의 반환값 처리 및 user_handle(0) 명시
        user_handle = 0
        result = self._plc.add_device_notification(symbol, attr, callback, user_handle)
        
        if isinstance(result, tuple):
            return result[0]
        return result # type: ignore

    # ==========================================================================
    # 상태 모니터링 (Read Feedback)
    # ==========================================================================
    def is_servo_on(self, axis_index: int) -> bool:
        """
        [상태 확인] 특정 축의 서보 전원(Servo ON) 상태를 확인한다.
        """
        return bool(self._plc.read_by_name(ServoSignal.SERVO_ON.get_plc_path(axis_index), pyads.PLCTYPE_BOOL))

    def is_servo_logic_busy(self, axis_index: int) -> bool:
        """
        [상태 확인] PLC 기능 블록이 명령을 처리 중인가? (Busy 비트 확인)
        """
        path = ServoSignal.BUSY.get_plc_path(axis_index)
        val = self._plc.read_by_name(path, pyads.PLCTYPE_BOOL)
        return bool(val)

    def read_current_servo_motion(self, axis_index: int) -> Dict[str, Any]:
        """
        [피드백] 현재 위치와 속도를 읽어온다.
        PLC: MAIN.Act_pos{i}, MAIN.Act_vel{i}
        오류 발생 시 예외 전파.
        """
        curr_pos = self._plc.read_by_name(ServoSignal.ACT_POS.get_plc_path(axis_index), pyads.PLCTYPE_LREAL)
        curr_vel = self._plc.read_by_name(ServoSignal.ACT_VEL.get_plc_path(axis_index), pyads.PLCTYPE_LREAL)
        return {'position': curr_pos, 'velocity': curr_vel}

    def is_servo_moving_physically(self, axis_index: int, threshold: float = 0.1) -> bool:
        """
        [상태 확인] 해당 축이 물리적으로 움직이고 있는가? (현재 속도를 측정해서 판단)
        
        Args:
            axis_index: 축 번호
            threshold: 움직임으로 판단할 속도 임계값 (deg/s)
        """
        feedback = self.read_current_servo_motion(axis_index)
        return abs(feedback['velocity']) > threshold

    def is_servo_error_active(self, axis_index: int) -> Dict[str, Any]:
        """
        [상태 확인] 해당 축에 에러가 발생했나 확인
        """
        try:
            # 보통 TwinCAT MC 블록은 bError(BOOL)와 nErrorID(UDINT/UINT)를 가집니다.
            # 경로가 설정되어 있지 않다면 ServoSignal 모델에 추가가 필요합니다.
            has_error = self._plc.read_by_name(f"MAIN.bError{axis_index}", pyads.PLCTYPE_BOOL)
            error_id = self._plc.read_by_name(f"MAIN.nErrorID{axis_index}", pyads.PLCTYPE_UINT)
            return {'error': has_error, 'id': error_id}
        except:
            return {'error': False, 'id': 0}

    def has_servo_error(self, axis_index: int) -> bool:
        """
        [상태 확인] 해당 축에 에러가 발생했는지 여부를 반환한다.
        PLC: MAIN.bError{i} (True: 에러 발생, False: 정상)
        """
        return bool(self._plc.read_by_name(
            ServoSignal.ERROR_STATE.get_plc_path(int(axis_index)), 
            pyads.PLCTYPE_BOOL
        ))

    def _get_servo_error_info(self, axis_index: int) -> Dict[str, Any]:
        """에러 상태와 ID를 읽어서 반환 (순수 데이터 조회)"""
        is_error = self.has_servo_error(axis_index)
        error_id = 0
        error_msg = "None"

        if is_error:
            error_id = self._plc.read_by_name(ServoSignal.ERROR_ID.get_plc_path(int(axis_index)), pyads.PLCTYPE_UDINT)
            
            # 에러 메시지 해석 (Adapter의 역할)
            if error_id == 1861:
                error_msg = "통신 시간 초과 (PLC 응답 없음). 네트워크 연결 상태를 확인해 주세요."
            elif error_id == 16992:
                error_msg = "서보 드라이브가 준비되지 않았습니다. 전원 공급 상태와 비상 정지 버튼을 확인한 후 'RESET'을 눌러주세요."
            else:
                error_msg = f"하드웨어 결함이 감지되었습니다 (에러 코드: {error_id})."
        
        return {
            'active': is_error,
            'id': error_id,
            'message': error_msg
        }



    # ==========================================================================
    # 이동 명령 (Write Command)
    # ==========================================================================
    def move_velocity(self, axis_index: int, target_velocity: float):
        """
        [속도 제어 이동] Tool 공전/자전용 (Axis 1, 2)
        특징: 목표 위치 없이 '속도'만 주고 계속 회전함 (bMoveVel)
        
        Args:
            axis_index: 축 번호
            target_velocity: 목표 속도 (deg/s) - 이미 스케일링 된 값
        """
        # 명령 받을 준비 됐는지 검증 - 검증 실패 시 상위 레이어로 전파됨
        # 속도 모드는 이동 중에도 속도 변경(Override)이 가능해야 하므로 Busy 허용
        self.validate_axis_ready(axis_index, allow_busy=True)

        plc = self._plc
        
        # 1. 속도 입력 (MAIN.vel{i})
        plc.write_by_name(ServoSignal.TARGET_VEL.get_plc_path(axis_index), target_velocity, pyads.PLCTYPE_LREAL)
        
        # 2. 속도 제어 트리거 ON (MAIN.bMoveVel{i})
        #    Latch 방식이므로 True로 유지
        plc.write_by_name(ServoSignal.MOVE_VEL.get_plc_path(axis_index), False, pyads.PLCTYPE_BOOL)
        plc.write_by_name(ServoSignal.MOVE_VEL.get_plc_path(axis_index), True, pyads.PLCTYPE_BOOL)

    def move_turntable_atomic(self, axis_index: int, target_pos: float, target_velocity: float):
        """
        턴테이블 독립 제어
            위치, 속도, 트리거를 한 번에(Batch) 전송
        """
        # 명령 받을 준비 됐는지 검증
        self.validate_axis_ready(axis_index)

        plc = self._plc
        
        # 1. 트리거 리셋 (0 -> 1 상승 엣지 신호를 만들기 위해 먼저 0으로 내림)
        trigger_path = ServoSignal.MOVE_ABS.get_plc_path(axis_index)
        plc.write_by_name(trigger_path, False, pyads.PLCTYPE_BOOL)
        
        # 2. 값 설정 및 출발 (위치, 속도, 출발 신호를 한 번에 묶어서 전송)
        # 위치, 속도, 트리거(ON)를 한 번에 전송
        plc.write_list_by_name({
            ServoSignal.TARGET_VEL.get_plc_path(axis_index): target_velocity,
            ServoSignal.TARGET_POS.get_plc_path(axis_index): target_pos,
            trigger_path: True
        })

    def execute_synchronized_motion(
        self, 
        turntable_moving_velocity: float, 
        turntable_target_position: float, 
        spindle_rotation_velocity: float, 
        spindle_revolution_velocity: float
    ):
        """
        [Sync Step 4: Synchronized Start] 3개 서보 축(공전/자전/턴테이블)에 대한 이동 명령을 원자적(Atomic)으로 동시 전송한다.
        
        '1년 뒤의 나'를 위한 설명:
            로봇과 서보가 모두 준비되었을 때(Step 3 완료), 이 메서드를 통해 실질적인 물리 구동을 시작한다.
            pyads의 write_list_by_name을 사용하여 통신 오버헤드를 최소화하고 3축이 동시 출발하도록 보장한다.
        
        Args:
            turntable_moving_velocity (float): 턴테이블의 회전 속도 (deg/s)
            turntable_target_position (float): 턴테이블의 목표 각도 (deg)
            spindle_rotation_velocity (float): 툴 자전 속도 (RPM -> deg/s 변환 전 원본 값)
            spindle_revolution_velocity (float): 툴 공전 속도 (RPM -> deg/s 변환 전 원본 값)
            
        Logic:
            1. Reset: 이전 동작의 Latch를 풀기 위해 모든 실행(Move) 및 정지(Stop) 신호를 False로 내린다.
            2. Set & Execute: 목표값들을 쓰고, 동시에 실행 비트(MoveVel/MoveAbs)를 True로 올려 구동을 시작한다.
            
        [Reference]
        [원본] 141: def execute_synchronized_motion(...)
        [원본] 341: motor_controller.execute_synchronized_motion(...)
        """
        plc = self._plc
        
        # 1. 동작 신호 초기화 (Rising Edge를 위한 준비)
        plc.write_list_by_name({
            'MAIN.bMoveVel1': False, 'MAIN.bMoveVel2': False, 'MAIN.bMoveAbs3': False,
            'MAIN.bStop1': False, 'MAIN.bStop2': False, 'MAIN.bStop3': False
        })
        
        # 2. 파라미터 업데이트 및 동시 실행 (Batch Write)
        # 툴 모터(Axis 1, 2)는 RPM 단위를 deg/s로 변환하기 위해 6.0배 스케일링을 수행함 (1 RPM = 6 deg/s)
        plc.write_list_by_name({
            'MAIN.vel3': float(turntable_moving_velocity),
            'MAIN.pos3': float(turntable_target_position),
            'MAIN.bMoveAbs3': True,
            
            'MAIN.vel2': float(spindle_rotation_velocity) * 6.0,
            'MAIN.bMoveVel2': True,
            
            'MAIN.vel1': float(spindle_revolution_velocity) * 6.0,
            'MAIN.bMoveVel1': True
        })

    def _homing(self, axis_index: int):
        """
        [원점 복구] 특정 축의 원점 복귀(Homing) 작업을 시작한다
        
        로봇팀 요구사항 반영:
            1. bHome 신호를 먼저 False로 초기화 (확실한 펄스 생성 위함)
            2. bHome 신호를 True로 인가하여 작업 시작 (완료 시 PLC가 자동으로 False로 복구함)
        """
        # 명령 받을 준비 됐는지 검증 - 검증 실패 시 상위 레이어로 전파됨
        self.validate_axis_ready(axis_index)

        plc = self._plc
        
        # Enum 객체가 들어올 경우를 대비해 int로 변환하여 주소 생성
        # 예: ServoAxis.TURNTABLE -> 3 -> "MAIN.bHome3"
        home_signal = ServoSignal.HOME.get_plc_path(int(axis_index))

        # 1. 선행 초기화: 먼저 False를 써줌 (로봇팀 가이드)
        plc.write_by_name(home_signal, False, pyads.PLCTYPE_BOOL)
        time.sleep(0.1) # 신호 안정화 대기
        
        # 2. 작업 시작: True 인가
        plc.write_by_name(home_signal, True, pyads.PLCTYPE_BOOL)



    def send_tt_target_data(self, target_data: Dict[str, float]):
        plc = self._plc
        plc.write_list_by_name({
            ServoSignal.SM_SINGLE_POS_VAR: target_data.get('tt_deg'),
            ServoSignal.SM_SINGLE_VEL_VAR: target_data.get('tt_feed_rate')
        })

    def trigger_tt_manual_move(self):
        plc = self._plc
        plc.write_by_name(ServoSignal.SM_SINGLE_START_VAR, True, pyads.PLCTYPE_BOOL)
        time.sleep(0.3)
        plc.write_by_name(ServoSignal.SM_SINGLE_START_VAR, False, pyads.PLCTYPE_BOOL)

    def reset_hand_shake_signals(self):
        plc = self._plc
        plc.write_by_name(ServoSignal.SM_VAR_ALL_FIN, False, pyads.PLCTYPE_BOOL)
        time.sleep(0.5)
        plc.write_by_name(ServoSignal.SM_VAR_UPD_DONE, False, pyads.PLCTYPE_BOOL)
        

    def SM_load_csv_data(self, sequences):
        data_list = []
        scale_factor = 0.995
        index = 0

        try:
            for index, sequence in enumerate(sequences):
                item = ST_PathData()

                val_velocity    = float(sequence.get('tt_feed_rate'))
                val_position    = float(sequence.get('tt_deg'))
                val_velocity2   = float(sequence.get('rev'))
                val_velocity3   = float(sequence.get('rot'))
                
                # 0번째 row는 턴테이블 움직임이 없으므로 건너뜀
                if index == 0 and val_position == 0.0:
                    continue

                item.fVelocity  = val_velocity * scale_factor
                item.fPosition  = val_position
                item.fVelocity2 = val_velocity2
                item.fVelocity3 = val_velocity3

                data_list.append(item)

            return data_list

        except Exception as e:
            raise RuntimeError(f"모터 시퀀스 데이터 변환 실패 (행 번호: {index}): {e}")

    def SM_send_buffer_chunk(self, start_idx_plc, py_data_chunk):
        """
        두 번째 시퀀스부터 (특정 갯수만큼=500개) 캐싱
        -> 첫 번째 row 제외 DUE TO 첫 번째 row는 턴테이블 움직임이 없기 때문
        """
        plc = self._plc

        count = len(py_data_chunk)
        if count == 0: return

        buffer_array = Array500()
        for i in range(count):
            buffer_array[i].fPosition   = py_data_chunk[i].fPosition
            buffer_array[i].fVelocity   = py_data_chunk[i].fVelocity
            buffer_array[i].fVelocity2  = py_data_chunk[i].fVelocity2
            buffer_array[i].fVelocity3  = py_data_chunk[i].fVelocity3            

        byte_data       = bytes(buffer_array)
        symbol_info = plc.get_symbol(ServoSignal.SM_VAR_PATH_ARR)
        
        # 타입 안전성 확보: index_group 과 index_offset 이 None인지 체크
        if symbol_info.index_group is None or symbol_info.index_offset is None:
            raise RuntimeError(f"[Servo] '{ServoSignal.SM_VAR_PATH_ARR}' 심볼 정보를 가져올 수 없습니다.")

        base_group: int = symbol_info.index_group
        base_offset: int = symbol_info.index_offset
        
        current_offset  = (start_idx_plc - 1) * ctypes.sizeof(ST_PathData)
        plc.write(base_group, base_offset + current_offset, byte_data, pyads.PLCTYPE_BYTE * len(byte_data))

    def watch_buffer_update(self, all_data: List[ST_PathData], current_ptr: int, check_interrupt: Callable[[], bool]):
        """
        서보 모터의 버퍼 갱신(Req Lower/Upper)을 무한 루프로 감시하며 데이터를 전송합니다.
        
        Args:
            all_data: 전체 서보 데이터 리스트
            current_ptr: 현재까지 전송된 데이터 인덱스
            check_interrupt: 스레드 중단 여부를 반환하는 콜백 함수
        """
        plc = self._plc
        total_len = len(all_data)

        while not check_interrupt():
            if current_ptr >= total_len:
                try:
                    if not plc.read_by_name(ServoSignal.SM_VAR_ALL_FIN, pyads.PLCTYPE_BOOL):
                        logger.info("[Servo] 모든 데이터 전송 완료. 종료 신호 전송.")
                        plc.write_by_name(ServoSignal.SM_VAR_ALL_FIN, True, pyads.PLCTYPE_BOOL)
                except Exception as e:
                    raise Exception(f"서보 데이터 전송 실패. 종료 신호 확인 실패 : {e}")
                time.sleep(1)
            
            try:
                # [하단 버퍼 업데이트 요청]
                if plc.read_by_name(ServoSignal.SM_VAR_REQ_LOWER, pyads.PLCTYPE_BOOL):
                    logger.debug("[Servo] Req Lower 감지 -> 버퍼 업데이트")
                    if current_ptr + 500 > total_len:
                        chunk = all_data[current_ptr : total_len]
                    else:
                        chunk = all_data[current_ptr : current_ptr + 500]
                    self.SM_send_buffer_chunk(1, chunk)
                    current_ptr += len(chunk)

                    plc.write_by_name(ServoSignal.SM_VAR_UPD_DONE, True, pyads.PLCTYPE_BOOL)
                    while plc.read_by_name(ServoSignal.SM_VAR_REQ_LOWER, pyads.PLCTYPE_BOOL) and not check_interrupt():
                        time.sleep(0.01)
                    plc.write_by_name(ServoSignal.SM_VAR_UPD_DONE, False, pyads.PLCTYPE_BOOL)

                # [상단 버퍼 업데이트 요청]
                if plc.read_by_name(ServoSignal.SM_VAR_REQ_UPPER, pyads.PLCTYPE_BOOL):
                    logger.debug("[Servo] Req Upper 감지 -> 버퍼 업데이트")
                    if current_ptr + 500 > total_len:
                        chunk = all_data[current_ptr : total_len]
                    else:
                        chunk = all_data[current_ptr : current_ptr + 500]
                    self.SM_send_buffer_chunk(501, chunk)
                    current_ptr += len(chunk)

                    plc.write_by_name(ServoSignal.SM_VAR_UPD_DONE, True, pyads.PLCTYPE_BOOL)
                    while plc.read_by_name(ServoSignal.SM_VAR_REQ_UPPER, pyads.PLCTYPE_BOOL) and not check_interrupt():
                        time.sleep(0.01)
                    plc.write_by_name(ServoSignal.SM_VAR_UPD_DONE, False, pyads.PLCTYPE_BOOL)

                time.sleep(0.005)

            except Exception as e:
                raise Exception(f"[Servo] 버퍼 업데이트 중 에러: {e}")
