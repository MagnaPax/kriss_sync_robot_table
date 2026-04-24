# communication/fanuc_adapter.py
import time
import pyads
import ctypes
from typing import TYPE_CHECKING, Union, Callable, Any
from communication.twincat_connector import TwinCATConnector
from models.fanuc_pose_key import FANUCPoseKey, FanucSignal
from models.fanuc_pose_model import FANUCPose
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

    def init_robot_signals(self):
        """로봇을 움직일 수 있는 신호로 초기화"""
        plc = self._plc
        plc.write_by_name(FanucSignal.IMSP.path, True, pyads.PLCTYPE_BOOL)
        plc.write_by_name(FanucSignal.HOLD.path, True, pyads.PLCTYPE_BOOL)
        plc.write_by_name(FanucSignal.SFSP.path, True, pyads.PLCTYPE_BOOL)
        plc.write_by_name(FanucSignal.ENABLE.path, True, pyads.PLCTYPE_BOOL)
        plc.write_by_name(FanucSignal.FAULT_RESET.path, True, pyads.PLCTYPE_BOOL)

    def reset_robot_fault(self):
        """Fault 신호 리셋"""
        plc = self._plc
        plc.write_by_name(FanucSignal.FAULT_RESET.path, True, pyads.PLCTYPE_BOOL)
        time.sleep(0.3)
        plc.write_by_name(FanucSignal.FAULT_RESET.path, False, pyads.PLCTYPE_BOOL)
        

    def set_emergency_stop(self):
        """[비상 정지]"""
        plc = self._plc
        plc.write_by_name(FanucSignal.IMSP.path, False, pyads.PLCTYPE_BOOL)

    def start_robot(self):
        """로봇 시작 신호 전송"""
        plc = self._plc
        plc.write_by_name(FanucSignal.HOLD.path, True, pyads.PLCTYPE_BOOL)
        plc.write_by_name(FanucSignal.START.path, True, pyads.PLCTYPE_BOOL)

    def stop_fanuc_normally(self):
        """로봇 정지 신호 전송"""
        plc = self._plc
        plc.write_by_name(FanucSignal.HOLD.path, False, pyads.PLCTYPE_BOOL)

    def back_to_fanuc_home(self):
        """로봇 원점 복귀 신호 전송"""
        plc = self._plc
        plc.write_by_name(FanucSignal.HOME.path, True, pyads.PLCTYPE_BOOL)
        time.sleep(0.3)
        plc.write_by_name(FanucSignal.HOME.path, False, pyads.PLCTYPE_BOOL)


    # ===================================================
    #       알림 (Notification)
    # ===================================================
    def remove_notification(self, handle: int):
        """[정리] 알림 해제 (공용)"""
        try:
            self._plc.del_device_notification(handle, 0)
        except Exception:
            pass


    # ===================================================
    #       상태 읽기 (Read): 기존 유지 (Bit-wise)
    # ===================================================
    def validate_robot_ready(self):
        """로봇이 명령을 수행할 수 있는 상태인지 검증"""
        if self.has_fault():
            raise RobotFaultError("로봇에 결함(Fault)이 감지되었습니다. 컨트롤러의 에러를 확인하고 리셋해 주세요.")

    def has_fault(self) -> bool:
        """로봇 에러 상태 확인"""
        return bool(self._plc.read_by_name(FanucSignal.FAULT_STATUS.path, pyads.PLCTYPE_BOOL))

    def read_busy_signal(self) -> bool:
        """로봇이 움직이고 있는지 확인"""



    # WORLD Coordinate: 로봇 발바닥(Base) 기준 절대 좌표
    # TOOL Coordinate : 로봇 손끝(TCP: Tool Center Point) 기준 좌표

    # ===================================================
    #                   모니터링
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


    # ==================
    #    메신저 이용        
    # ==================
    def prepare_chunk_buffers(self, total_data: list[dict[str, float]], current_idx: int, buf_size: int) -> list[list[float]]:
        """[데이터 분할] 전체 데이터에서 150개씩 잘라서 PLC 전송용 버퍼(3개)로 나눈다."""

        chunk = total_data[current_idx : current_idx + buf_size]

        serialized = []
        for item in chunk:
            serialized.extend([item['dx'], item['dz'], item['fd']])

        needed_len = buf_size * 3
        if len(serialized) < needed_len:
            serialized.extend([0.0] * (needed_len - len(serialized))) 

        # 450개를 150개씩(BUFFER_SIZE) 3등분
        return [
            serialized[0:FanucSignal.BUFFER_SIZE],
            serialized[FanucSignal.BUFFER_SIZE:FanucSignal.BUFFER_SIZE*2],
            serialized[FanucSignal.BUFFER_SIZE*2:FanucSignal.BUFFER_SIZE*3]
        ]

    def send_to_plc_group(self, group_num: int, buffers: list[list[float]]):
        """[PLC 전송] 3개의 버퍼 데이터를 PLC의 지정된 그룹(1 or 2)에 쓴다."""
        plc = self._plc
        
        # 1. 버퍼 데이터 쓰기
        # MAIN.send_buffer{group_num}_{buffer_index} (1~3)
        prefix = f'MAIN.send_buffer{group_num}_'
        plc.write_list_by_name({
            f'{prefix}1': buffers[0],
            f'{prefix}2': buffers[1],
            f'{prefix}3': buffers[2]
        })

        # 2. 버퍼 ID 및 Attribute 설정 (Loop)
        start_idx = 0 if group_num == 1 else 3

        nInstance = (buf_size << 8) | 0x01

        # PLC의 배열에 데이터 전송 및 Send 실행
        for i in range(start_idx, start_idx + 3):
            buf_id, start_pt = FanucSignal.BUFFER_MAPPING.value[i] if hasattr(FanucSignal.BUFFER_MAPPING, 'value') else FanucSignal.BUFFER_MAPPING[i]

            plc.write_list_by_name({
                FanucSignal.SERVICE_CODE.path : 0x33,
                FanucSignal.CLASS.path        : 0x6C,
                FanucSignal.INSTANCE.path     : nInstance,
                FanucSignal.ATTRIBUTE.path    : start_pt,
                FanucSignal.BUFFER_ID.path    : buf_id
            })
            
            # Execute Pulse
            plc.write_by_name(FanucSignal.EXECUTE.path, True, pyads.PLCTYPE_BOOL)
            time.sleep(0.35)
            plc.write_by_name(FanucSignal.EXECUTE.path, False, pyads.PLCTYPE_BOOL)
            time.sleep(0.35)

    def send_to_plc_info(self, group_num: int, buffers:list[list[float]]):
        plc = self._plc

        total_valid_items = 0
        for buf in buffers:
            total_valid_items += (len(buf) - buf.count(0.0))
        data_rows = total_valid_items // 3

        counter_idx = 0x394 if group_num == 1 else 0x395    # Data Counter를 보내기 위한 Attribute(0x394 = 916(R[916]에 저장) / 0x395 = 917(R[917]에 저장))
        
        # 데이터 정보(개수) 전송 및 Send 실행
        plc.write_list_by_name({
            FanucSignal.SERVICE_CODE.path     : 0x10,
            FanucSignal.CLASS.path            : 0x6B,
            FanucSignal.INSTANCE.path         : 0x01,
            FanucSignal.ATTRIBUTE_SINGLE.path : counter_idx,  # Attribute (e.g., 993, 983)
            FanucSignal.NUMBER_OF_DATA.path   : data_rows,    # Data 정보(개수)
            FanucSignal.BUFFER_ID.path        : 99,
        })

        plc.write_by_name(FanucSignal.EXECUTE.path, True, pyads.PLCTYPE_BOOL)
        time.sleep(0.3)
        plc.write_by_name(FanucSignal.EXECUTE.path, False, pyads.PLCTYPE_BOOL)

    def send_target_data_to_plc_buffer(self, targets, BUFFER_TYPE: str):
        plc = self._plc

        targets = self._refine_robot_targets(targets)

        plc.write_by_name(BUFFER_TYPE, targets, pyads.PLCTYPE_REAL * 7)

        plc.write_list_by_name({
            FanucSignal.SERVICE_CODE.path     : 0x33,
            FanucSignal.CLASS.path            : 0x6C,
            FanucSignal.INSTANCE.path         : 0x0701,
            FanucSignal.ATTRIBUTE.path        : 0x3A3,
            FanucSignal.BUFFER_ID.path        : 2
        })
        plc.write_by_name(FanucSignal.EXECUTE.path, True, pyads.PLCTYPE_BOOL)
        time.sleep(0.35)
        plc.write_by_name(FanucSignal.EXECUTE.path, False, pyads.PLCTYPE_BOOL)

    def trigger_move_signal(self, RSR_VAR: str, wait_time: float=1.0):
        """FANUC TP 프로그램 실행 신호 전송
        Args:
            RSR_VAR: 
                'MAIN.Robot1._UI1.UI09_RSR1': FANUC TP 프로그램 시작 - 시퀀스용
                'MAIN.Robot1._UI1.UI10_RSR2': FANUC TP 프로그램 시작 - 단독 동작용
            wait_time: 신호 전송 후 대기 시간
        """
        plc = self._plc

        plc.write_by_name(RSR_VAR, True, pyads.PLCTYPE_BOOL)
        time.sleep(wait_time)
        plc.write_by_name(RSR_VAR, False, pyads.PLCTYPE_BOOL)


    # ==================
    #       헬퍼
    # ==================
    def _refine_robot_targets(self, targets: Union[list, dict, FANUCPose]) -> list[float]:
        """
        로봇이 사용할 수 있는 데이터로 변환
        
        Input 지원 형식:
        1. List[float]: [x, y, z, w, p, r, f] (7개 실수) -> 그대로 반환
        2. FANUCPose: 객체의 속성값 추출
        3. Dict: {'x': 10, ...} -> FANUCPose 변환 후 추출
        4. List[Dict]: 시퀀스 데이터인 경우, 첫 번째 포인트만 추출 (Goto 모드)
        """
        # 1. 리스트인 경우
        if isinstance(targets, list):
            if not targets:
                raise ValueError("Targets list is empty")
            
            # 1-1. 숫자 리스트 (단일 포인트 raw data)
            if isinstance(targets[0], (int, float)):
                # 부족하면 0.0 채우기 or 잘라내기? 일단 있는 대로 변환
                return [float(v) for v in targets]
            
            # 1-2. 딕셔너리 리스트 (시퀀스 데이터) -> 첫 번째 포인트만 사용
            return self._refine_robot_targets(targets[0])

        # 2. FANUCPose 객체
        if isinstance(targets, FANUCPose):
            return [targets.x, targets.y, targets.z, targets.w, targets.p, targets.r, targets.f]

        # 3. 딕셔너리
        if isinstance(targets, dict):
            # 호환성: feed_rate 키가 있으면 f로 매핑
            if 'feed_rate' in targets and 'f' not in targets:
                targets['f'] = targets['feed_rate']

            pose = FANUCPose.from_dict(targets)
            return [pose.x, pose.y, pose.z, pose.w, pose.p, pose.r, pose.f]

        raise TypeError(f"Unsupported type for targets: {type(targets)}")
