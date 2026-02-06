# communication/fanuc_adapter.py
import time
import pyads
import ctypes
from typing import TYPE_CHECKING, Union, Callable, Any
from communication.twincat_connector import TwinCATConnector
from models.fanuc_pose_key import FANUCPoseKey, FanucSignal
from models.fanuc_pose_model import FANUCPose, FanucCommandPacket
from core.exceptions import RobotFaultError
from core.exceptions import RobotFaultError
from utils.logger import get_logger

logger = get_logger(__name__)

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


    # ===================================================
    #           쓰기 (Write): 구조체 전송
    # ===================================================
    def write_command_packet(self, packet: FanucCommandPacket):
        """
        [핵심] 명령 패킷(구조체)을 PLC에 전송
        """
        log_msg = self._format_packet_log(packet)
        logger.debug(log_msg)
        # 구조체 타입(FanucCommandPacket)을 명시적으로 전달해야 함
        # pyads의 write_by_name은 ctypes.Structure 타입을 인자로 받을 수 있지만, 
        # 타입 힌트가 엄격하게 정의되어 있어서 Any로 캐스팅하여 에러를 우회함
        self._plc.write_by_name("MAIN.Robot1._UI1", packet, FanucCommandPacket) # type: ignore

    def send_instant_feed(self, feed_rate: float):
        """
        [속도 변경] 이동 중인 비트스트림의 Feed Rate 부분을 즉시 수정하여 반영
        Reference: FanucPose.to_struct()
        """
        plc = self._plc
        
        # 1. 값 변환: float -> scaled int
        raw_feed_rate = int(abs(round(feed_rate, 3) * 1000))
        
        # 2. Feed_Low (하위 16비트) 즉시 쓰기
        feed_low = raw_feed_rate & 0xFFFF
        plc.write_by_name("MAIN.Robot1._UI1.Feed_Low", feed_low, pyads.PLCTYPE_UINT)
        
        # 3. UI_Byte3 (상위 4비트) Read-Modify-Write
        #    기존 신호(Start, DI44 등)가 하위 4비트에 있으므로 보존해야 함
        current_ui3 = plc.read_by_name("MAIN.Robot1._UI1.UI_Byte3", pyads.PLCTYPE_BYTE)
        
        feed_high = (raw_feed_rate >> 16) & 0x0F
        new_ui3 = (current_ui3 & 0x0F) | (feed_high << 4)
        
        plc.write_by_name("MAIN.Robot1._UI1.UI_Byte3", new_ui3, pyads.PLCTYPE_BYTE)

    def set_emergency_stop(self):
        """[비상 정지] IMSP 신호 전송"""
        emergency_stop_cmd_signals = {
            FanucSignal.IMSP: False, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
            FanucSignal.CYCLE_STOP: False, FanucSignal.START: False, FanucSignal.RSR2: False, FanucSignal.RSR3: False, FanucSignal.TRIGGER_DI43: False
        }
        # 비상 정지 시 로봇 좌표는 의미가 없으므로 '신호 전송용 패킷'을 생성해서 보낸다
        # 'IMSP' 신호를 확실하게 전달하는 것이 핵심
        packet = FANUCPose.create_signal_only_packet(emergency_stop_cmd_signals)
        self.write_command_packet(packet)        

    def set_initial_signals(self):
        """[초기화] 로봇 시작 신호 초기화 (RSR2=False, DI43=False 등)"""
        cmd_signals = {
            FanucSignal.IMSP: True, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
            FanucSignal.CYCLE_STOP: False, FanucSignal.START: False, FanucSignal.RSR2: False, FanucSignal.RSR3: False, FanucSignal.TRIGGER_DI43: False
        }
        # 로봇을 움직이려는 게 아니라 초기화 신호(Reset)만 보냄
        # 따라서 좌표값은 의미가 없으므로 '신호 전송용 패킷'을 생성해서 보낸다
        packet = FANUCPose.create_signal_only_packet(cmd_signals)
        self.write_command_packet(packet)
        time.sleep(0.05)

    def write_initial_signals(self):
        """(Legacy Alias)"""
        self.set_initial_signals()

    def stop_fanuc_normally(self):
        stop_cmd_signals = {
            FanucSignal.IMSP: True, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
            FanucSignal.CYCLE_STOP: True, FanucSignal.START: False, FanucSignal.RSR2: False, FanucSignal.RSR3: False, FanucSignal.TRIGGER_DI43: False
        }
        # 정지할 때 로봇 좌표는 의미가 없으므로 '신호 전송용 패킷'을 생성해서 보낸다
        packet = FANUCPose.create_signal_only_packet(stop_cmd_signals)
        self.write_command_packet(packet)

    def back_to_fanuc_home(self):
        """[복귀] 로봇 원점 복귀 신호 전송"""
        cmd_signals = {
            FanucSignal.IMSP: True, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
            FanucSignal.CYCLE_STOP: False, FanucSignal.START: False, FanucSignal.HOME: True, FanucSignal.RSR2: False, FanucSignal.RSR3: False, FanucSignal.TRIGGER_DI43: False
        }
        # 원점 복귀할 때 로봇 좌표는 의미가 없으므로 '신호 전송용 패킷'을 생성해서 보낸다
        packet = FANUCPose.create_signal_only_packet(cmd_signals)
        self.write_command_packet(packet)


    # ===================================================
    #       알림 (Notification): 완료 신호 감지
    # ===================================================
    def register_robot_motion_done_callback(self, callback: Callable[..., Any]) -> int:
        """
        로봇이 시퀀스(한 줄)을 받았다는 확인 신호(DO46)를 감지하기 위한 이벤트를 등록한다.
        [원본] robot.add_notification(SYM_DO46, cb_motion_done)
        
            동시 동기 구동(Hand-in-hand)을 위해, 로봇과 서보(턴테이블)가 모두 이동을 마쳤는지 확인할 때 사용된다.
            이 신호가 확인된 후에야 비로소 다음 스텝을 위한 'Sync Start Trigger(DI44)'를 보낼 수 있다.
        """
        return self._register_notification(FanucSignal.ROBOT_MOTION_DONE.value, callback)

    def _register_notification(self, symbol: str, callback: Callable[[Any, Any], None]) -> int:
        """(내부 헬퍼) ADS 알림 등록 공통 로직"""
        attr = pyads.NotificationAttrib(ctypes.sizeof(pyads.PLCTYPE_BOOL))
        # pyads.NotificationAttrib 속성에 대한 타입 힌트 오류 무시
        attr.nTransMode = pyads.ADSTRANS_SERVERONCHA # type: ignore
        attr.nCycleTime = 100000 # type: ignore
        attr.nMaxDelay = 0 # type: ignore
        
        # add_device_notification의 반환값 처리 및 user_handle(0) 명시
        user_handle = 0
        result = self._plc.add_device_notification(symbol, attr, callback, user_handle)
        
        if isinstance(result, tuple):
            return result[0]
        return result # type: ignore

    def remove_notification(self, handle: int):
        """[정리] 알림 해제 (공용)"""
        try:
            self._plc.del_device_notification(handle, 0)
        except Exception:
            pass

    def remove_handshake_callback(self, handle: int):
        # FanucOnlyExecutor에서 호출할 때 특정 심볼을 지우려고 시도할 수 있으므로
        # remove_notification 공용 메서드를 사용하도록 유도
        self.remove_notification(handle)
        
    def write_synchronization_start_trigger(self, state: bool):
        """
        [Sync Step 4: Sync Start Trigger] 로봇과 서보의 동시 출발을 위한 트리거(DI44)를 전송한다.
        """
        self.write_digital_signal(FanucSignal.LOOP_DI44, state)

    def write_digital_signal(self, signal: Union[FanucSignal, str], value: bool):
        """
        [공용] 디지털 신호(Bit) 쓰기
        Args:
            signal: FanucSignal Enum 또는 문자열 주소
            value: True/False
        """
        path = signal.value if isinstance(signal, FanucSignal) else signal
        self._plc.write_by_name(path, value, pyads.PLCTYPE_BOOL)



    # ===================================================
    #       상태 읽기 (Read): 기존 유지 (Bit-wise)
    # ===================================================
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
        return bool(self._plc.read_by_name(FanucSignal.ROBOT_MOTION_DONE.path, pyads.PLCTYPE_BOOL))


    # WORLD 좌표: 로봇 발바닥(Base) 기준 절대 좌표
    # TOOL 좌표: 로봇 손끝(TCP: Tool Center Point) 기준 좌표

    # ===================================================
    #           피드백 데이터 읽기
    # ===================================================
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

    # ===================================================
    #   모니터링 데이터 읽기 <- 값 확인하는 디버깅 용
    # ===================================================
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


    # ==================
    #       헬퍼        
    # ==================
    def _format_packet_log(self, packet: FanucCommandPacket) -> str:
        """
        [로깅 헬퍼] FanucCommandPacket을 사람이 읽기 편한 문자열로 변환 (비트 디코딩 포함)
        
        전달 신호로 사용되는 바이트(UI_Byte1, UI_Byte2, Check_Bits)는 비트 단위로 풀어서 보여준다.
        """
        lines = []
        lines.append(f"plc에 쓸 패킷: {packet} 타입: {type(packet)}")
        
        # 1. UI_Byte1 (Control Signals)
        # 128 64 32 16 8 4 2 1
        # [7] [6] [5] [4] [3] [2] [1] [0] 
        ui1 = packet.UI_Byte1
        lines.append(f"  - UI_Byte1: {ui1} (0x{ui1:02X})")
        lines.append(f"    - IMSP:       {'True' if (ui1 & 1) else 'False'}")   # Bit 0
        lines.append(f"    - Hold:       {'True' if (ui1 & 2) else 'False'}")   # Bit 1
        lines.append(f"    - SFSPD:      {'True' if (ui1 & 4) else 'False'}")   # Bit 2
        lines.append(f"    - Cycle Stop: {'True' if (ui1 & 8) else 'False'}")   # Bit 3
        lines.append(f"    - Fault Reset:{'True' if (ui1 & 16) else 'False'}")  # Bit 4
        lines.append(f"    - Start:      {'True' if (ui1 & 32) else 'False'}")  # Bit 5
        lines.append(f"    - Home:       {'True' if (ui1 & 64) else 'False'}")  # Bit 6
        lines.append(f"    - Enable:     {'True' if (ui1 & 128) else 'False'}") # Bit 7

        # 2. UI_Byte2 (RSR Signals)
        ui2 = packet.UI_Byte2
        lines.append(f"  - UI_Byte2: {ui2} (0x{ui2:02X})")
        for i in range(8):
            mask = 1 << i
            lines.append(f"    - RSR{i+1}:       {'True' if (ui2 & mask) else 'False'}")

        # 3. UI_Byte3 (사용하지 않는 신호 + 이동시작 + 루프 + Feed Rate)
        ui3 = packet.UI_Byte3
        lines.append(f"  - UI_Byte3: {ui3} (0x{ui3:02X})")
        lines.append(f"    - PNStrobe:         {'True' if (ui3 & 1) else 'False'}")   # Bit 0
        lines.append(f"    - Prod start:       {'True' if (ui3 & 2) else 'False'}")   # Bit 1
        lines.append(f"    - DI43:             {'True' if (ui3 & 4) else 'False'}")   # Bit 2
        lines.append(f"    - DI44:             {'True' if (ui3 & 8) else 'False'}")   # Bit 3
        lines.append(f"    - F00:              {'True' if (ui3 & 16) else 'False'}")  # Bit 4
        lines.append(f"    - F01:              {'True' if (ui3 & 32) else 'False'}")  # Bit 5
        lines.append(f"    - F02:              {'True' if (ui3 & 64) else 'False'}")  # Bit 6
        lines.append(f"    - F03:              {'True' if (ui3 & 128) else 'False'}") # Bit 7

        # 4. Check_Bits (Negative Checks)
        chk = packet.Check_Bits
        lines.append(f"  - Check_Bits: {chk} (0x{chk:02X})")
        axis_names = ['X', 'Y', 'Z', 'W', 'P', 'R']
        for i, name in enumerate(axis_names):
            mask = 1 << i   # Check_X is Bit 0
            lines.append(f"    - Check_{name}:   {'True' if (chk & mask) else 'False'}")

        # 5. 축 데이터 (X, Y, Z, W, P, R) 상세 출력
        #    사용자 요청 포맷: 값 계산 후 High, Low 표시
        axis_names = ['X', 'Y', 'Z', 'W', 'P', 'R']
        for i, axis in enumerate(axis_names):
            high = getattr(packet, f"{axis}_High")
            low = getattr(packet, f"{axis}_Low")
            
            # 값 복원 (High * 65536 + Low) / 1000
            raw_val = (high * 65536) + low
            float_val = raw_val / 1000.0
            
            # 음수 체크 (Check_Bits 해당 비트가 1이면 음수)
            if (packet.Check_Bits >> i) & 1:
                float_val = -float_val

            lines.append(f"  - 실제 이동할 {axis} 거리 (입력값-사용자좌표): {float_val}")
            lines.append(f"    - {axis}_High:   {high}")
            lines.append(f"    - {axis}_Low:    {low}")

        # 6. 나머지 필드 (Feed_Low 등)
        completed_fields = {'UI_Byte1', 'UI_Byte2', 'UI_Byte3', 'Check_Bits'}
        # 축 관련 필드도 이미 찍었으므로 제외
        for axis in axis_names:
            completed_fields.add(f"{axis}_High")
            completed_fields.add(f"{axis}_Low")
            
        for field in packet._fields_:
            field_name = field[0]
            if field_name in completed_fields:
                continue
            value = getattr(packet, field_name)
            lines.append(f"  - {field_name:<10}: {value}")
            
        return "\n".join(lines)




    # ==================
    #    메신저 이용        
    # ==================
    
    def prepare_chunk_buffers(self,total_data, current_idx, buf_size):
        """배열에 데이터 저장(dx1, dz1, fd1, dx2, dz2, fd2, ...)"""
        chunk = total_data[current_idx : current_idx + buf_size]

        serialized = []
        for item in chunk:
            serialized.extend([item['dx'], item['dz'], item['fd']])

        needed_len = buf_size * 3
        if len(serialized) < needed_len:
            serialized.extend([0.0] * (needed_len - len(serialized))) 

        return [
            serialized[0:150],
            serialized[150:300],
            serialized[300:450]
        ]

    def send_to_plc_group(self, group_num, buffers):
        """PLC에 전송"""
        plc = self._plc

        print(f" >> [Group {group_num}] 데이터 전송 및 트리거 실행 시작")

        total_valid_items = 0
        for buf in buffers:
            total_valid_items += (len(buf) - buf.count(0.0))
        data_rows = total_valid_items // 3

        if group_num == 1:
            plc.write_list_by_name({
                FanucSignal.FIRST_BUFFER_1: buffers[0],
                FanucSignal.FIRST_BUFFER_2: buffers[1],
                FanucSignal.FIRST_BUFFER_3: buffers[2]
            })
        else:
            plc.write_list_by_name({
                FanucSignal.SECOND_BUFFER_1: buffers[0],
                FanucSignal.SECOND_BUFFER_2: buffers[1],
                FanucSignal.SECOND_BUFFER_3: buffers[2]
            })

        start_idx = 0       if group_num == 1 else 3
        counter_idx = 0x3E1 if group_num == 1 else 0x3D7    # Data Counter를 보내기 위한 Attribute(0x3E1 = 993(R[993]에 저장) / 0x3D7 = 983(R[983]에 저장장))

        # PLC의 배열에 데이터 전송 및 Send 실행
        for i in range(start_idx, start_idx + 3):
            buf_id, start_pt = FanucSignal.BUFFER_MAPPING[i]

            plc.write_list_by_name({
                FanucSignal.BUFFER_ID : buf_id,
                FanucSignal.ATTRIBUTE : start_pt
            })
            plc.write_by_name(FanucSignal.EXECUTE, True, pyads.PLCTYPE_BOOL)
            time.sleep(0.4)
            plc.write_by_name(FanucSignal.EXECUTE, False, pyads.PLCTYPE_BOOL)
            time.sleep(0.4)
        
        # 데이터 정보(개수) 전송 및 Send 실행
        plc.write_list_by_name({
            FanucSignal.ATTRIBUTE_SINGLE: counter_idx,      # Attribute (e.g., 993, 983)
            FanucSignal.NUMBER_OF_DATA  : data_rows,        # Data 정보(개수)
            FanucSignal.EXECUTE_SINGLE  : True
        })
        time.sleep(0.5)
        plc.write_by_name(FanucSignal.EXECUTE_SINGLE, False, pyads.PLCTYPE_BOOL)

