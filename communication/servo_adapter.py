# communication/turntable_adapter.py
import time
import pyads
from typing import TYPE_CHECKING, Union, Dict, Any
from communication.twincat_connector import TwinCATConnector
from models.servo_pose_key import ServoSignal
from models.servo_pose_key import ServoAxis
from core.exceptions import ServoBusyError, ServoFaultError



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
        
        Args:
            axis_index (int): 축 번호 (1, 2, 3)
            enable (bool): True(ON) / False(OFF)
        """
        plc = self._plc
        
        # 1. 서보 전원 (bServoOn)
        plc.write_by_name(ServoSignal.SERVO_ON.get_plc_path(axis_index), enable, pyads.PLCTYPE_BOOL)
        
        # 2. 피드백 읽기 활성화 (bReadPos, bReadVel)
        #    원본 1219_Test.py의 Servo_Read_On 함수 로직 이식
        plc.write_by_name(ServoSignal.READ_POS_ON.get_plc_path(axis_index), enable, pyads.PLCTYPE_BOOL)
        plc.write_by_name(ServoSignal.READ_VEL_ON.get_plc_path(axis_index), enable, pyads.PLCTYPE_BOOL)

        # 신호 안정화 대기 (하드웨어 특성 고려)
        time.sleep(0.05)

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
        [상태 확인] 해당 축이 물리적으로 움직이고 있는가? (속도 기준)
        
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

    def move_absolute(self, axis_index: int, target_pos: float, target_velocity: float):
        """
        [위치 제어 이동] 턴테이블용 (Axis 3)
        특징: 목표 '위치'로 이동 후 멈춤 (bMoveAbs)
        
        Args:
            axis_index: 축 번호
            target_pos: 목표 각도 (deg)
            target_velocity: 이동 속도 (deg/s)
        """
        # 명령 받을 준비 됐는지 검증 - 검증 실패 시 상위 레이어로 전파됨
        self.validate_axis_ready(axis_index)

        plc = self._plc

        # 1. 목표 위치 입력 (MAIN.pos{i})
        plc.write_by_name(ServoSignal.TARGET_POS.get_plc_path(axis_index), target_pos, pyads.PLCTYPE_LREAL)

        # 2. 이동 속도 입력 (MAIN.vel{i})
        plc.write_by_name(ServoSignal.TARGET_VEL.get_plc_path(axis_index), target_velocity, pyads.PLCTYPE_LREAL)
        
        # 3. 절대 이동 트리거 (Pulse)
        #    Rising Edge(False -> True)를 만들어야 확실하게 동작함
        plc.write_by_name(ServoSignal.MOVE_ABS.get_plc_path(axis_index), False, pyads.PLCTYPE_BOOL)
        plc.write_by_name(ServoSignal.MOVE_ABS.get_plc_path(axis_index), True, pyads.PLCTYPE_BOOL)

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
