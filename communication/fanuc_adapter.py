# communication/fanuc_adapter.py
import time
import pyads
import ctypes
from typing import TYPE_CHECKING, Union, Dict, Callable
from communication.twincat_connector import TwinCATConnector
from models.fanuc_pose_key import FANUCPoseKey, FanucSignal
from models.fanuc_pose_model import FANUCPose, FanucCommandPacket
from core.exceptions import RobotFaultError

# 실제 런타임에는 실행 안 됨
# 타입 검사기(Pylance)에게만 MockConnection의 존재를 알려줌
# 순환 참조(Circular Import) 오류를 방지하면서 타입 힌트를 제공하기 위함
if TYPE_CHECKING:
    from communication.mock_plc import MockConnection


class FanucAdapter:
    """
    FANUC 로봇 통신 로직을 담당하는 Model(도메인 + 프로토콜) 레이어
    
    [역할]
    - "손과 발": 스스로 판단하지 않고, 외부(Commander)에서 시키는 대로 I/O를 수행함.
    - 데이터 변환: 도메인 객체(FANUCPose) <-> PLC Raw Data 변환
    
    [통신 프로토콜: Full Threading Logic 2025]
    1. 쓰기 (Write): 
        - 24byte 구조체(FanucCommandPacket)를 한 번에 전송.
        - 개별 비트 제어(Bit-banging) 방식 폐기됨.
    2. 읽기 (Read): 
        - 기존의 비트 단위 읽기 로직 유지 (로봇 팀의 Output 구조체가 정의되지 않음).
    3. 핸드셰이킹 (Handshake):
        - Polling(계속 물어보기) 방식 폐기됨.
        - Event-driven: register_handshake_callback()을 통해 Rising Edge 알림을 받음.
    """
    def __init__(self, connector: TwinCATConnector):
        # 지갑(Connector)을 받아서 저장
        self.connector = connector

        # 사용자 입력에 의해 바뀐 이동 속도 저장
        self.override_feed_rate: Union[float, None] = None


    @property
    def _plc(self) -> Union[pyads.Connection, 'MockConnection']:
        """
        Connector의 활성 핸들을 가져오는 단축 속성

        사용 예:
            self._plc : TwinCATConnector.handle 실행돼서 _twincat(트윈캣 핸들) 반환됨
        """
        return self.connector.handle


    # ==========================================================================
    # 1. 쓰기 (Write): 구조체 전송
    # ==========================================================================
    def write_command_packet(self, packet: FanucCommandPacket):
        """
        [핵심] 명령 패킷(구조체)을 PLC에 전송
        
        [Reference]
        원본 파일: FANUC_SYNC_CLEAN_renamed(260105).py
        [원본] 88: def send_robot_command_packet(self, symbol, payload)
        [원본] 296, 322, 339: robot_controller.send_robot_command_packet(...)
        """
        # 구조체 타입(FanucCommandPacket)을 명시적으로 전달해야 함
        self._plc.write_by_name("MAIN.Robot1._UI1", packet, FanucCommandPacket)

    def set_emergency_stop(self):
        """[비상 정지] IMSP 신호 전송"""
        emergency_stop_cmd_signals = {
            FanucSignal.IMSP: False, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
            FanucSignal.CYCLE_STOP: False, FanucSignal.START: False, FanucSignal.RSR2: False, FanucSignal.RSR3: False, FanucSignal.DATA_READY_DI43: False
        }
        # 비상 정지 시 로봇 좌표는 의미가 없으므로 '신호 전송용 패킷'을 생성해서 보낸다
        # 'IMSP' 신호를 확실하게 전달하는 것이 핵심
        packet = FANUCPose.create_signal_only_packet(emergency_stop_cmd_signals)
        self.write_command_packet(packet)        

    def set_initial_signals(self):
        """[초기화] 로봇 시작 신호 초기화 (RSR2=False, DI43=False 등)"""
        cmd_signals = {
            FanucSignal.IMSP: True, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
            FanucSignal.CYCLE_STOP: False, FanucSignal.START: False, FanucSignal.RSR2: False, FanucSignal.RSR3: False, FanucSignal.DATA_READY_DI43: False
        }
        # 로봇을 움직이려는 게 아니라 초기화 신호(Reset)만 보냄
        # 따라서 좌표값은 의미가 없으므로 '신호 전송용 패킷'을 생성해서 보낸다
        packet = FANUCPose.create_signal_only_packet(cmd_signals)
        self.write_command_packet(packet)
        time.sleep(0.05)

    def set_finish_signals(self):
        """[종료] 로봇 시퀀스 종료 신호 전송 (RSR2=False)"""
        # 초기화와 거의 동일하게 모든 시작 신호를 끔
        self.set_initial_signals()

    def write_initial_signals(self):
        """(Legacy Alias)"""
        self.set_initial_signals()




    # ==========================================================================
    # 2. 알림 (Notification): 완료 신호 감지
    # [원본] 96: def add_device_notification(self, symbol, callback)
    # ==========================================================================

    def register_calculation_request_callback(self, callback: Callable) -> int:
        """
        [Sync Step 1: Calculation Request] 로봇의 계산 요청(DO45) 신호를 감지하기 위한 이벤트를 등록한다.
        [원본] 430: handle_calc = robot.add_device_notification(SYM_CALC_REQUEST, handle_calculation_request)
        
        로봇 PLC가 다음 스텝의 경로 데이터를 계산해달라고 요청할 때 이 알림(Rising Edge)이 발생한다.
        이 알림이 오면 파이썬(Commander)은 즉시 다음 좌표를 로봇에게 전송(Pre-load)해야 한다.
            
        Args:
            callback: 
                신호 변화 시 실행될 함수. (notification, data) 형태의 인자를 받음.
            
        Returns:
            int: 이 알림을 나중에 해제할 때 사용할 핸들(Handle) 번호.
        """
        return self._register_notification(FanucSignal.CALCULATION_REQUEST.value, callback)

    def register_robot_motion_done_callback(self, callback: Callable) -> int:
        """
        [Sync Step 3: Robot Motion Done] 로봇의 물리적 이동 완료(DO46) 신호를 감지하기 위한 이벤트를 등록한다.
        [원본] 384: handle_motion = robot.add_device_notification(SYM_ROBOT_MOTION_DONE, handle_robot_motion_done)
        
            로봇이 목표 위치에 실제로 도착했을 때 이 알림이 발생한다.
            동시 동기 구동(Hand-in-hand)을 위해, 로봇과 서보(턴테이블)가 모두 이동을 마쳤는지 확인할 때 사용된다.
            이 신호가 확인된 후에야 비로소 다음 스텝을 위한 'Sync Start Trigger(DI44)'를 보낼 수 있다.
        """
        return self._register_notification(FanucSignal.ROBOT_MOTION_DONE.value, callback)

    def _register_notification(self, symbol: str, callback: Callable) -> int:
        """(내부 헬퍼) ADS 알림 등록 공통 로직"""
        attr = pyads.NotificationAttrib(ctypes.sizeof(pyads.PLCTYPE_BOOL))
        attr.nTransMode = pyads.ADSTRANS_SERVERONCHA # 값이 바뀔 때마다 알림
        attr.nCycleTime = 100000 # 10ms (100ns 단위)
        attr.nMaxDelay = 0
        return self._plc.add_device_notification(symbol, attr, callback)

    def remove_notification(self, handle: int):
        """[정리] 알림 해제 (공용)"""
        try:
            self._plc.del_device_notification(handle)
        except Exception:
            pass

    # 구버전 호환성 유지 (Reference: FanucOnlyExecutor)
    # FanucOnlyExecutor는 아직 'Handshake'라는 용어를 사용하므로 Alias 제공
    def register_handshake_callback(self, callback: Callable) -> int:
        """(호환성 유지용) 구버전 연동을 위해 calculation_request_callback으로 연결함"""
        return self.register_calculation_request_callback(callback)
    
    def remove_handshake_callback(self, handle: int):
        # FanucOnlyExecutor에서 호출할 때 특정 심볼을 지우려고 시도할 수 있으므로
        # remove_notification 공용 메서드를 사용하도록 유도
        self.remove_notification(handle)
        
    def write_synchronization_start_trigger(self, state: bool):
        """
        [Sync Step 4: Sync Start Trigger] 로봇과 서보의 동시 출발을 위한 트리거(DI44)를 전송한다.
        """
        self.write_digital_signal(FanucSignal.SYNC_START_TRIGGER_DI44, state)

    def write_digital_signal(self, signal: Union[FanucSignal, str], value: bool):
        """
        [공용] 디지털 신호(Bit) 쓰기
        Args:
            signal: FanucSignal Enum 또는 문자열 주소
            value: True/False
        """
        path = signal.value if isinstance(signal, FanucSignal) else signal
        self._plc.write_by_name(path, value, pyads.PLCTYPE_BOOL)



    # ==========================================================================
    # 3. 상태 읽기 (Read): 기존 유지 (Bit-wise)
    # ==========================================================================
    # 로봇팀 코드에 '읽기(Output)'용 구조체 정의가 없으므로,
    # 기존에 잘 동작하던 비트 읽기 방식을 유지하는 것이 가장 안전함.
    
    def validate_robot_ready(self):
        """로봇이 명령을 수행할 수 있는 상태인지 검증"""
        if self.has_fault():
            raise RobotFaultError("로봇에 결함(Fault)이 감지되었습니다. 컨트롤러의 에러를 확인하고 리셋해 주세요.")

    def has_fault(self) -> bool:
        """로봇 에러 상태 확인 (UO06_Fault)"""
        return bool(self._plc.read_by_name(FanucSignal.FAULT.path, pyads.PLCTYPE_BOOL))

    def read_busy_signal(self) -> bool:
        """로봇이 움직이고 있는지 확인"""
        return bool(self._plc.read_by_name(FanucSignal.BUSY.path, pyads.PLCTYPE_BOOL))
    
    # (주의) read_complete_signal은 이제 Notification(Callback) 방식으로 대체되므로
    # 직접 폴링(Polling)할 일은 줄어들겠지만, 상태 확인용으로 남겨둠.
    def read_complete_signal(self) -> bool:
        return bool(self._plc.read_by_name(FanucSignal.COMPLETE.path, pyads.PLCTYPE_BOOL))


    # WORLD 좌표: 로봇 발바닥(Base) 기준 절대 좌표
    # TOOL 좌표: 로봇 손끝(TCP: Tool Center Point) 기준 좌표

    # ==========================================================================
    # 4. 피드백 데이터 읽기
    # ==========================================================================
    """
    목적:           로봇이 "실제로 어디에 있는가?" 확인
    데이터 방향:    로봇 → PLC (로봇이 보고함)
    용도:           UI에 현재 로봇 위치 표시, 작업 완료 확인
    """
    def _read_axis_value(self, key: FANUCPoseKey) -> float:
        """
        [헬퍼] 특정 축(Key)의 현재 값을 PLC에서 비트 단위로 읽어와 실수로 변환
            로봇 피드백 데이터를 24비트/1000 스케일로 읽기
            예외 발생 시 상위로 전파됨
        """
        plc = self._plc

        # 1. 상위 8비트 읽기 (High Byte: h0 ~ h7)
        top_val = 0
        for i in range(8):
            # key.feedback_tag_high_bit(i) -> Removed from model, constructing manual string
            path = f"MAIN.Robot1._UO1.{key.value}h{i}"
            if plc.read_by_name(path, pyads.PLCTYPE_BOOL):
                top_val |= (1 << i)

        # 2. 하위 16비트 읽기 (Low Word: l0 ~ l15)
        low_val = 0
        for j in range(16):
            path = f"MAIN.Robot1._UO1.{key.value}l{j}"
            if plc.read_by_name(path, pyads.PLCTYPE_BOOL):
                low_val |= (1 << j)

        # 3. 비트 합치기 (24비트)
        raw_val = (top_val << 16) | low_val

        # 4. 부호 확인
        path_check = f"MAIN.Robot1._UO1.{key.value}_Check"
        is_negative = plc.read_by_name(path_check, pyads.PLCTYPE_BOOL)

        # 5. 스케일링 (1/1000)
        scaled_val = raw_val / 1000.0

        if is_negative:
            scaled_val = -scaled_val

        return round(scaled_val, 3)

    def read_current_world_pose(self) -> FANUCPose:
        """현재 World 좌표 읽기"""
        return FANUCPose(
            x = self._read_axis_value(FANUCPoseKey.X),
            y = self._read_axis_value(FANUCPoseKey.Y),
            z = self._read_axis_value(FANUCPoseKey.Z),
            w = self._read_axis_value(FANUCPoseKey.W),
            p = self._read_axis_value(FANUCPoseKey.P),
            r = self._read_axis_value(FANUCPoseKey.R)
        )

    # ==========================================================================
    # 5. 모니터링 데이터 읽기 <- 값 확인하는 디버깅 용
    # ==========================================================================
    """
    목적:           PLC가 로봇에게 "어디로 가라고 시켰는가?" 확인
    데이터 방향:    PLC → 로봇 (PLC가 명령함)
    용도:           내가 보낸 명령이 PLC 레지스터에 잘 써졌는지 검증
    """    
    def _read_target_axis_value(self, key: FANUCPoseKey) -> float:
        """
        [헬퍼] PLC가 로봇에게 명령 중인 목표값(UI1)을 읽어옴
        """
        plc = self._plc

        # 1. 상위 8비트 읽기 (High Byte)
        top_val = 0
        for i in range(8):
            # tag_high_bit 메서드가 모델에서 삭제되었으므로, 여기서 문자열 f-string으로 복구하거나
            # 모델 Key에 다시 추가해야 하는데... 
            # 모델 Key에서 삭제했으므로 여기서 직접 문자열 조합을 사용 (Legacy 호환)
            path = f"MAIN.Robot1._UI1.{key.value}h{i}"
            if plc.read_by_name(path, pyads.PLCTYPE_BOOL):
                top_val |= (1 << i)

        # 2. 하위 16비트 읽기 (Low Word)
        low_val = 0
        for j in range(16):
            path = f"MAIN.Robot1._UI1.{key.value}l{j}"
            if plc.read_by_name(path, pyads.PLCTYPE_BOOL):
                low_val += (1 << j)

        # 3. 비트 합치기
        raw_val = (top_val << 16) + low_val
        path = f"MAIN.Robot1._UI1.{key.value}_Check"
        is_negative = plc.read_by_name(path, pyads.PLCTYPE_BOOL)

        # 5. 스케일링
        scaled_val = raw_val / 1000.0
        if is_negative: scaled_val = -scaled_val
        return round(scaled_val, 3)

    def read_target_world_pose(self) -> FANUCPose:
        """현재 PLC 레지스터에 기록된 '목표 위치' 읽기"""
        return FANUCPose(
            x = self._read_target_axis_value(FANUCPoseKey.X),
            y = self._read_target_axis_value(FANUCPoseKey.Y),
            z = self._read_target_axis_value(FANUCPoseKey.Z),
            w = self._read_target_axis_value(FANUCPoseKey.W),
            p = self._read_target_axis_value(FANUCPoseKey.P),
            r = self._read_target_axis_value(FANUCPoseKey.R)
        )


# ==========================================================
# Smoke Test
# ==========================================================
if __name__ == '__main__':
    from communication.mock_plc import MockConnection
    from unittest.mock import MagicMock

    print("=" * 70)
    print("FanucAdapter 단독 실행 테스트 (Mock)")
    print("=" * 70)

    # 1. Mock Connector 생성
    mock_connector = MagicMock(spec=TwinCATConnector)
    mock_plc = MagicMock(spec=MockConnection)
    mock_connector.handle = mock_plc
    
    adapter = FanucAdapter(mock_connector)
    print("✅ Adapter 생성 완료")

    # 2. write_command_packet 테스트
    print("\n[Test 1] write_command_packet")
    dummy_pose = FANUCPose(x=10.0, y=20.0, z=30.0, w=0, p=0, r=0, f=100.0)
    dummy_packet = dummy_pose.to_struct(dummy_pose, {'Start': True})
    
    adapter.write_command_packet(dummy_packet)
    
    # Verify: write_by_name called with struct
    args, _ = mock_plc.write_by_name.call_args
    # args[0] should be "MAIN.Robot1._UI1"
    # args[1] should be the packet
    # args[2] should be FanucCommandPacket type
    print(f"   Call args: {args}")
    assert args[0] == "MAIN.Robot1._UI1"
    assert isinstance(args[1], FanucCommandPacket)
    assert args[2] == FanucCommandPacket
    print("✅ write_command_packet 호출 검증 성공")

    # 3. register_handshake_callback 테스트
    print("\n[Test 2] register_handshake_callback")
    def my_callback(n, d):
        pass
    
    adapter.register_handshake_callback(my_callback)
    
    # Verify: add_device_notification called
    args, _ = mock_plc.add_device_notification.call_args
    print(f"   Call args: {args}")
    assert args[0] == FanucSignal.COMPLETE.value # "MAIN.Robot1._UO1.DO45"
    assert args[2] == my_callback
    print("✅ register_handshake_callback 호출 검증 성공")

    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)
