# communication/turntable_adapter.py
import time
import pyads
from typing import TYPE_CHECKING, Union, Tuple
from communication.twincat_connector import TwinCATConnector
from models.servo_pose_key import ServoPoseKey, ServoSignal
from models.servo_pose_model import ServoPose
from models.servo_pose_key import ServoAxis



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
        plc.write_by_name(ServoSignal.SERVO_ON.path(axis_index), enable, pyads.PLCTYPE_BOOL)
        
        # 2. 피드백 읽기 활성화 (bReadPos, bReadVel)
        #    원본 1219_Test.py의 Servo_Read_On 함수 로직 이식
        plc.write_by_name(ServoSignal.READ_POS_ON.path(axis_index), enable, pyads.PLCTYPE_BOOL)
        plc.write_by_name(ServoSignal.READ_VEL_ON.path(axis_index), enable, pyads.PLCTYPE_BOOL)

        # 신호 안정화 대기 (하드웨어 특성 고려)
        time.sleep(0.05)

    def clear_error_pulse(self, axis_index: int) -> bool:
        """
        [에러 초기화] bReset 신호를 발생시켜 축의 에러 상태를 해제한다
            bReset=True 후 다시 False로 초기화 필수
        """
        plc = self._plc
        try:
            # 1. 에러 상태가 아니면 리셋 절차를 수행할 필요가 없음
            if not self.has_servo_error(axis_index): return True

            # 2. 리셋 명령 - bReset: True -> Wait -> False
            plc.write_by_name(ServoSignal.ERROR_RESET.path(axis_index), True, pyads.PLCTYPE_BOOL)   # True
            time.sleep(0.2) # Wait: PLC가 리셋을 인식할 시간 확보
            plc.write_by_name(ServoSignal.ERROR_RESET.path(axis_index), False, pyads.PLCTYPE_BOOL)  # False
            
            # 3. 실제로 에러가 해제되었는지 확인
            time.sleep(0.1)
            is_cleared = not self.has_servo_error(axis_index)
            if is_cleared:
                EVENT_BUS.log.message.emit(f"서보 {axis_index}축 리셋 성공", "INFO")
            return is_cleared

        except Exception as e:
            EVENT_BUS.log.message.emit(f"서보 {axis_index}축 리셋 실패: {e}", "ERROR")
            return False

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
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 전체 원점 복귀 시작...", "INFO")

        try:
            # 1. 선행 조치: 현재 동작 중단
            self.request_immediate_stop()
            time.sleep(0.5) # 정지 후 안정화 대기

            # 2. 모든 축에 원점 복귀 명령 전송 (bHome False -> True)
            for axis in ServoAxis:
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] {axis.name}(Axis {axis.value}) 원점 신호 전송", "DEBUG")
                self._homing(axis)
            
            # 명령이 반영되어 물리적 이동이 시작될 때까지 잠시 대기
            time.sleep(0.5)

            # 3. 정지 완료 대기
            start_time = time.time()
            while time.time() - start_time < timeout:
                # 모든 축 중 하나라도 움직이고 있는지 '물리적'으로 체크
                is_any_moving = any(self.is_servo_moving_physically(axis) for axis in ServoAxis)
                
                if not is_any_moving:
                    EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 모든 축 원점 복귀 완료", "INFO")
                    return True
                
                # 아직 움직이는 중...
                time.sleep(0.2)

            # 4. 타임아웃 발생 시
            EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 원점 복귀 시간 초과 ({timeout}s)", "WARNING")
            self.request_immediate_stop() # 안전을 위해 다시 정지 시도
            return False

        except Exception as e:
            EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 원점 복귀 중 에러 발생: {e}", "ERROR")
            return False



    # ==========================================================================
    # 안전 정지 (Stop & Safety)
    # ==========================================================================
    def stop_axis(self, axis_index: int):
        """
        [개별 정지] 특정 축을 안전하게 정지시킨다.
        원본 1219_Test.py의 's' 키 입력 시 동작 로직을 그대로 구현함.
        
        시퀀스:
            1. 이동 신호(MoveVel/MoveAbs) 끄기 (Latch 해제)
            2. 정지 신호(bStop) 켜기
            3. 0.5초 대기 (감속 및 정지 시간 확보)
            4. 정지 신호(bStop) 끄기 (Reset)
        """
        plc = self._plc

        # 1. 이동 신호 해제 (Latch 풀기)
        #    속도 제어용(Axis 1,2)과 위치 제어용(Axis 3) 신호를 구분하여 해제
        if axis_index in [1, 2]:
            plc.write_by_name(ServoSignal.MOVE_VEL.path(axis_index), False, pyads.PLCTYPE_BOOL)
        elif axis_index == 3:
            plc.write_by_name(ServoSignal.MOVE_ABS.path(axis_index), False, pyads.PLCTYPE_BOOL)
        
        # 2. 정지 신호 인가 (bStop = True)
        plc.write_by_name(ServoSignal.STOP.path(axis_index), True, pyads.PLCTYPE_BOOL)
        
        # 3. 물리적 감속 대기 (원본 코드의 time.sleep(0.5) 반영)
        time.sleep(0.5)
        
        # 4. 정지 신호 해제 (다시 움직일 수 있게 준비)
        plc.write_by_name(ServoSignal.STOP.path(axis_index), False, pyads.PLCTYPE_BOOL)

    def request_immediate_stop(self):
        """모든 축에 정지 명령 내림"""
        plc = self._plc

        # (A) 모든 축 이동 해제 & 정지 신호 ON
        for i in ServoAxis:
            if i in [ServoAxis.TOOL_REVOLUTION, ServoAxis.TOOL_ROTATION]:
                plc.write_by_name(ServoSignal.MOVE_VEL.path(i), False, pyads.PLCTYPE_BOOL)
            elif i == ServoAxis.TURNTABLE:
                plc.write_by_name(ServoSignal.MOVE_ABS.path(i), False, pyads.PLCTYPE_BOOL)
            
            plc.write_by_name(ServoSignal.STOP.path(i), True, pyads.PLCTYPE_BOOL)
        
        # (B) 물리적 감속을 위한 공통 대기 (원본 코드 0.5초 준수)
        time.sleep(0.5)

        # (C) 정지 신호 해제 (다음 동작이 가능하도록 Reset)
        for i in ServoAxis:
            plc.write_by_name(ServoSignal.STOP.path(i), False, pyads.PLCTYPE_BOOL)

    def shutdown_all_with_power_off(self, timeout: float = 3.0):
        """정지 확인 후 전원까지 차단"""
        try:
            # 1. 정지 명령 내림
            self.request_immediate_stop()

            # 2. 모든 축의 속도가 임계값 이하로 떨어질 때까지 대기
            start_time = time.time()
            while time.time() - start_time < timeout:
                # 모든 축이 속도 임계값(is_servo_moving_physically) 이하인지 체크
                if not any(self.is_servo_moving_physically(i) for i in ServoAxis):
                    break
                time.sleep(0.1)

            # 3. 모든 축 서보 전원 차단
            for i in ServoAxis:
                self.set_servo_state(i, False)
            return True

        except Exception as e:
            return False



    # ==========================================================================
    # 상태 모니터링 (Read Feedback)
    # ==========================================================================
    def is_servo_logic_busy(self, axis_index: int) -> bool:
        """
        [상태 확인] PLC 기능 블록이 명령을 처리 중인가? (Busy 비트 확인)
        """
        path = ServoSignal.BUSY.path(axis_index)
        val = self._plc.read_by_name(path, pyads.PLCTYPE_BOOL)
        return bool(val)

    def read_current_servo_motion(self, axis_index: int) -> dict:
        """
        [피드백] 현재 위치와 속도를 읽어온다.
        PLC: MAIN.Act_pos{i}, MAIN.Act_vel{i}
        오류 발생 시 예외 전파.
        """
        curr_pos = self._plc.read_by_name(ServoSignal.ACT_POS.path(axis_index), pyads.PLCTYPE_LREAL)
        curr_vel = self._plc.read_by_name(ServoSignal.ACT_VEL.path(axis_index), pyads.PLCTYPE_LREAL)
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

    def is_servo_error_active(self, axis_index: int) -> dict:
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
        try:
            return self._plc.read_by_name(
                ServoSignal.ERROR_STATE.path(axis_index), 
                pyads.PLCTYPE_BOOL
            )
        except Exception as e:
            # 통신 오류 발생 시 안전을 위해 에러 상태인 것으로 간주하거나 로그를 남김
            EVENT_BUS.log.message.emit(f"서보 {axis_index}축 에러 상태 읽기 실패: {e}", "WARNING")
            return True

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
        plc = self._plc
        
        # 1. 속도 입력 (MAIN.vel{i})
        plc.write_by_name(ServoSignal.TARGET_VEL.path(axis_index), target_velocity, pyads.PLCTYPE_LREAL)
        
        # 2. 속도 제어 트리거 ON (MAIN.bMoveVel{i})
        #    Latch 방식이므로 True로 유지
        plc.write_by_name(ServoSignal.MOVE_VEL.path(axis_index), False, pyads.PLCTYPE_BOOL)
        time.sleep(0.1)
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

    def _homing(self, axis_index: int):
        """
        [원점 복구] 특정 축의 원점 복귀(Homing) 작업을 시작합니다.
        
        로봇팀 요구사항 반영:
            1. bHome 신호를 먼저 False로 초기화 (확실한 펄스 생성 위함)
            2. bHome 신호를 True로 인가하여 작업 시작
            (완료 시 PLC가 자동으로 False로 복구함) [cite: 9]
        """
        plc = self._plc
        
        # Enum 객체가 들어올 경우를 대비해 int로 변환하여 주소 생성
        # 예: ServoAxis.TURNTABLE -> 3 -> "MAIN.bHome3"
        signal_path = ServoSignal.HOME.path(int(axis_index))

        try:
            # 1. 선행 초기화: 먼저 False를 써줌 (로봇팀 가이드)
            plc.write_by_name(signal_path, False, pyads.PLCTYPE_BOOL)
            time.sleep(0.1) # 신호 안정화 대기
            
            # 2. 작업 시작: True 인가
            plc.write_by_name(signal_path, True, pyads.PLCTYPE_BOOL) [cite: 9]
            
            EVENT_BUS.log.message.emit(f"서보 {axis_index}축 원점 복귀 명령 전송 완료", "DEBUG")
            
        except Exception as e:
            EVENT_BUS.log.message.emit(f"서보 {axis_index}축 원점 복귀 명령 실패: {e}", "ERROR")
            raise
