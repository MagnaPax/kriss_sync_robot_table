# communication/twincat_commander.py
"""
TwinCAT Commander (Model Layer)
    전략 패턴(Strategy Pattern) 사용

    역할:
        TwinCAT 에 연결된 기기(FANUC 로봇, 턴테이블) 제어
"""
import time
import pyads
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Union, TYPE_CHECKING, Callable, List, Any

from core.event_bus import EVENT_BUS
from communication.fanuc_adapter import FanucAdapter
from communication.twincat_connector import TwinCATConnector
from communication.turntable_adapter import TurntableAdapter
from models.fanuc_pose_model import FANUCPose
from models.turntable_pose_model import TurntablePose



# 타입 검사기(Pylance)에게만 MockConnection의 존재를 알려줌
# 순환 참조(Circular Import) 오류를 방지하면서 타입 힌트를 제공하기 위해
if TYPE_CHECKING:
    from communication.mock_plc import MockConnection


# =========================================================
# 1. 추상 실행기 (Base Executor)
# =========================================================
class BaseExecutor(ABC):
    def __init__(self, robot: FanucAdapter, turntable: TurntableAdapter):
        self.robot = robot
        self.table = turntable

    @abstractmethod
    def can_execute(self, sample_data: dict) -> bool:
        """이 데이터 형식을 처리할 수 있는지 확인"""
        pass

    @abstractmethod
    def execute(self, sequence_data: list[dict]) -> tuple[bool, str]:
        """실제 실행 로직"""
        pass


# =========================================================
# 2. 전략 구현 (Strategies)
# =========================================================

class FanucOnlyExecutor(BaseExecutor):
    """로봇 단독 제어"""

    def can_execute(self, sample_data: dict) -> bool:
        # FANUCPose 객체의 키들이 포함되어 있는지 확인
        required_keys = {'w', 'p', 'r'} 
        return required_keys.issubset(sample_data.keys())

    def execute(self, sequence_data: list[dict]) -> tuple[bool, str]:
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 데이터\n{(sequence_data)}\n", "DEBUG")
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] FANUC 단독 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")

        # 처리할 전체 시퀀스 데이터 방송
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        adapter = self.robot

        # 사용자 입력 feed rate 초기화 (새 작업 시작이기 때문)
        adapter.override_feed_rate = None

        num_sequences = len(sequence_data)  # 전체 시퀀스 갯수

        try:
            init_done = False       # 첫 번째 명령을 보냈는지 확인하는 Flag
            previous_coords = None  # 이전 명령

            # 1. 초기 신호 전송
            adapter.set_initial_signals()

            # 2. 시퀀스 루프
            for idx, row in enumerate(sequence_data, 1):

                # 데이터에 'id'가 있으면 가져오고, 없다면 루프 인덱스(idx)를 id로 사용
                current_id = row.get('id') or idx

                # 현재 시퀀스 진행상태 방송: 진행중
                EVENT_BUS.data.progress_updated.emit(current_id, num_sequences, "processing")

                # 이동 속도
                if adapter.override_feed_rate is not None:
                    # 사용자가 '지금' 바꾼 FEED RATE
                    feed_rate = adapter.override_feed_rate
                else:
                    # GO TO 버튼 눌렀을 때 입력한 FEED RATE
                    feed_rate = row.get('f', 10.0)

                # 현재 좌표

                current_coords = {
                    'x': row['x'], 'y': row['y'], 'z': row['z'],
                    'w': row['w'], 'p': row['p'], 'r': row['r']
                }

                target_pose = FANUCPose(
                x=row.get('x', 0.0), y=row.get('y', 0.0), z=row.get('z', 0.0),
                w=row.get('w', 0.0), p=row.get('p', 0.0), r=row.get('r', 0.0),
                f=row.get('f', 0.0)
                )
                # 현재 로봇 위치 방송
                EVENT_BUS.control.robot_current_pose.emit(target_pose)


                # --- 증분 이동(Incremental/Relative Move) 제어 --- #
                # TP 프로그램이 Absolute 가 아닌 Relative 로 설정되어 있음

                # 첫 번째 시퀀스
                if previous_coords is None:
                    # 이동량(deltas)을 현재 좌표 그대로 설정
                    deltas = current_coords.copy()
                    # 기준점 업데이트
                    previous_coords = current_coords.copy()

                # 첫 번째 시퀀스 아니면
                else:
                    # 이동해야 될 양 = (현재 목표 - 직전 목표)
                    deltas = {key: current_coords[key] - previous_coords[key] for key in current_coords}

                    # 기준점 업데이트 (이번 목표가 다음번의 기준이 됨)
                    previous_coords = current_coords.copy()


                # --- 핸드셰이킹 (Busy Check) --- #
                while True:
                    # 로봇이 움직이는 중인지 확인
                    is_busy = adapter.read_busy_signal()

                    # 로봇이 움직이는 동안(Busy) 미리 다음 명령을 전송한다
                    #   -> 멈추지 않는 연속적인 동작을 위해
                    if (not init_done) or is_busy:
                        adapter.send_data_packet(feed_rate, deltas)

                        init_done = True    # 첫 번째 명령 실행했다고 체크
                        time.sleep(0.01)    # 통신 안정화

                        # 다음 시퀀스로 이동
                        break
                    else:
                        # 아직 준비 안 됨 -> 대기
                        time.sleep(0.01)

                # 현재 시퀀스 진행상태 방송: 완료
                EVENT_BUS.data.progress_updated.emit(current_id, num_sequences, "processed")

            # 3. 종료 신호
            adapter.set_finish_signals()
            return True, "작업 완료"
        
        except Exception as e:
            adapter.set_emergency_stop()
            return False, f"실행 중 에러 발생: {e}"


class IntegratedExecutor(BaseExecutor):
    """
    CSV 파일 형식 (로봇 + 턴테이블 통합 제어)
    """
    def can_execute(self, sample_data: dict) -> bool:
        # CSV_SCHEMA의 키들이 포함되어 있는지 확인
        required_keys = {'polar_coord_theta', 'polar_coord_radius'}
        return required_keys.issubset(sample_data.keys())

    def execute(self, sequence_data: list[dict]) -> tuple[bool, str]:
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] CSV 파일 통합 제어 모드로 실행 (데이터 {len(sequence_data)}건)", "INFO")

        # 처리할 전체 시퀀스 데이터 방송
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)
        
        """
        # 1. 시작 신호
        self.robot.start_sequence_plc_signals()
        # self.table.start_signal()

        # 2. 통합 루프
        for row in sequence_data:
            # 동기화 및 전송 로직...

            current_id = row.get('id')

            # TODO: current_id 를 이벤트 버스에 실어서 방송하기
            pass
        
        # 3. 종료 신호
        self.robot.end_sequence_plc_signals()
        """
        return True, "통합 제어 실행 완료 (구현 필요)"


class LegacyIntegratedExecutor(BaseExecutor):
    """
    레거시 TXT 파일 형식
    """

    def can_execute(self, sample_data: dict) -> bool:
        # TXT_SCHEMA의 키들이 포함되어 있는지 확인
        required_keys = {'turntable_deg', 'tool_rotation_rpm', 'tool_revolution_rpm'}
        return required_keys.issubset(sample_data.keys())

    def execute(self, sequence_data: list[dict]) -> tuple[bool, str]:
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 레거시 파일 모드로 실행 (데이터 {len(sequence_data)}건)", "INFO")

        # 처리할 전체 시퀀스 데이터 방송
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)        

        return True, "레거시 파일 모드 실행 완료 -> TODO: 로직 만들어야 된다"


class TurntableOnlyExecutor(BaseExecutor):
    """
    턴테이블 단독 제어
    용도: 턴테이블 테스트, 수동 이동 등
    """
    
    def can_execute(self, sample_data: dict) -> bool:
        # TurntablePose의 필수 키만 있고 로봇 데이터가 없는 경우
        # (로봇 데이터와 섞이면 IntegratedExecutor나 Legacy가 처리해야 함)
        
        # 필수 키: angle(또는 T), velocity
        has_turntable = 'angle' in sample_data or 'T' in sample_data
        
        # 로봇 키가 없어야 함 (있으면 복합 제어)
        has_robot = 'x' in sample_data or 'X' in sample_data
        
        return has_turntable and not has_robot

    def execute(self, sequence_data: list[dict]) -> tuple[bool, str]:
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 턴테이블 단독 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")

        # 처리할 전체 시퀀스 데이터 방송
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        adapter = self.table # TurntableAdapter
        num_sequences = len(sequence_data)

        try:
            # 1. 초기 신호 (Servo On, 초기화)
            adapter.set_initial_signals()
            
            init_done = False

            # 2. 시퀀스 루프
            for idx, row in enumerate(sequence_data, 1):
                
                current_id = row.get('id') or idx

                # 현재 시퀀스 진행상태 방송: 진행중
                EVENT_BUS.data.progress_updated.emit(current_id, num_sequences, "processing")
                
                # 데이터 추출 (키 매핑)
                angle_val = float(row.get('angle') or row.get('T', 0.0))
                velocity_val = float(row.get('velocity') or row.get('turntable_feed_rate', 10.0))

                # 현재 턴테이블 위치 방송
                target_pose = TurntablePose(angle=angle_val, velocity=velocity_val)
                EVENT_BUS.control.turntable_current_pose.emit(target_pose)


                # --- 핸드셰이킹 (Busy Check) ---
                while True:
                    # 턴테이블 Busy 확인
                    is_busy = adapter.read_busy_signal()
                    
                    # 턴테이블은 로봇과 달리 '멈추면 다음 명령(Stop-and-Go)' 방식이 더 안전할 수 있음
                    # 하지만 연속 동작을 원한다면 로봇과 동일하게 (not init_done or is_busy) 사용
                    if not is_busy:
                        # 1. 이동 명령 전송 (Rising Edge 발생)
                        adapter.move_to(angle_val, velocity_val)
                        
                        init_done = True
                        
                        # 2. 이동이 시작될 때까지(Busy=True) 잠시 대기
                        # (Adapter 내부에서 sleep을 주긴 했지만 안전장치)
                        time.sleep(0.2) 
                        
                        # 3. 이동이 끝날 때까지 대기 (Blocking)
                        # 단독 테스트이므로 확실하게 이동 완료 후 다음 명령 수행
                        while adapter.read_busy_signal():
                            time.sleep(0.1)
                        
                        break # 이동 완료 -> 다음 시퀀스
                    
                    else:
                        time.sleep(0.1)

                # 현재 시퀀스 진행상태 방송: 완료
                EVENT_BUS.data.progress_updated.emit(current_id, num_sequences, "processed")

            # 3. 종료 신호 (서보 오프 등)
            adapter.set_finish_signals()
            return True, "턴테이블 작업 완료"

        except Exception as e:
            adapter.set_emergency_stop()
            return False, f"턴테이블 실행 중 에러: {e}"


# =========================================================
# 3. 게이트웨이 (The Commander)
# =========================================================
class TwinCATCommander:

    def __init__(self, connector: TwinCATConnector):
        self.connector = connector
        
        # 하위 장치 컨트롤러
        self.robot = FanucAdapter(connector)
        self.turntable = TurntableAdapter(connector)

        # 등록된 실행기들 (우선순위 순서대로)
        self.executors: List[BaseExecutor] = [
            LegacyIntegratedExecutor(self.robot, self.turntable),   # 특정 키값이 더 많은 것을 먼저 검사
            IntegratedExecutor(self.robot, self.turntable),
            FanucOnlyExecutor(self.robot, self.turntable),  # x,y,z 중복된 키값이 많은 조건을 마지막에
            TurntableOnlyExecutor(self.robot, self.turntable)
        ]

    def execute_sequence_with_executor(self, sequence_data: list[dict[str, Any]]) -> tuple[bool, str]:
        """
        데이터 형식에 따라 적절한 Executor를 선택하여 실행하는 [게이트웨이]
            1. 데이터의 첫 줄을 샘플로 채취하여 적절한 실행기를 찾는다
            2. 찾은 Executor를 실행한다
        """
        if not sequence_data:
            return False, "데이터가 비어있습니다."

        sample_row = sequence_data[0]

        print(f"\n샘플 데이터: {sample_row}\n")
        
        # 1. 적절한 Executor 찾기
        target_executor = None
        for executor in self.executors:
            if executor.can_execute(sample_row):
                target_executor = executor
                break

        # 2. 찾은 Executor에게 실행 위임
        if target_executor:
            return target_executor.execute(sequence_data)
        else:
            return False, "지원하지 않는 데이터 형식입니다."

    def apply_user_feed_rate_when_moving(self, feed_rate: float) -> str | None:
        """TargetPositionWidget 에서 사용자가 입력한 Feed Rate 값을 FANUC에 적용"""

        is_moving = self.robot.read_busy_signal()
        if is_moving:
            # FANUC의 이동속도 변경
            self.robot.send_instant_feed(feed_rate)

            # FanucAdapter 변수에 저장
            # Executor가 다음 루프부터 참조할 수 있게 하기 위함
            self.robot.override_feed_rate = feed_rate

            msg = f"사용자에 의한 이동 속도 변경: {feed_rate} mm/sec"
            return msg
        else:
            return None