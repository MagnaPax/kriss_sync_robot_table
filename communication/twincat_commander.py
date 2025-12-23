# communication/twincat_commander.py
"""
TwinCAT Commander (Model Layer)
    전략 패턴(Strategy Pattern) 사용

    역할:
        TwinCAT 에 연결된 기기(FANUC 로봇, 턴테이블) 제어
"""
import time
from PyQt6.QtCore import QThread, QObject
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Any

from core.event_bus import EVENT_BUS
from communication.fanuc_adapter import FanucAdapter
from communication.servo_adapter import ServoAdapter
from communication.twincat_connector import TwinCATConnector
from models.fanuc_pose_model import FANUCPose
from models.servo_pose_model import ServoPose, ServoPoseModel
from config.data_formats import TaskStatus, SERVO_KEYS, ROBOT_KEYS



# 타입 검사기(Pylance)에게만 MockConnection의 존재를 알려줌
# 순환 참조(Circular Import) 오류를 방지하면서 타입 힌트를 제공하기 위해
if TYPE_CHECKING:
    from communication.mock_plc import MockConnection


# =========================================================
# 1. 추상 실행기 (Base Executor)
# =========================================================
class BaseExecutor(ABC):
    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        self.robot = robot
        self.servo = servo

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
        data_keys = set(sample_data.keys())
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        # 로봇 키가 있고, 서보 키는 없을 때
        return has_robot and not has_servo

    def execute(self, sequence_data: list[dict]) -> tuple[bool, str]:
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] FANUC 단독 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 에서 처리될 전체 데이터\n{(sequence_data)}\n", "DEBUG")

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
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 현재 시퀀스 진행상태: {(current_id)}", "DEBUG")


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
                EVENT_BUS.log.message.emit(f"\n현재 로봇 위치: {target_pose}\n", "DEBUG")


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
                    # 로봇이 작업을 잘 마쳤는지 확인
                    is_complete = adapter.read_complete_signal()

                    # 로봇이 움직이는 동안(Digital Output 45번 핀) 미리 다음 명령을 전송한다
                    #   -> 멈추지 않는 연속적인 동작을 위해
                    if (not init_done) or is_complete:
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


class ServoOnlyExecutor(BaseExecutor):
    """
    [서보 모터 전용 실행기]
    로봇 없이 Panasonic 서보 모터 3축(툴 2개 + 턴테이블 1개)만 단독 제어
    """

    # 타임아웃 상수
    BUSY_WAIT_TIMEOUT = 5.0   # 명령 후 Busy가 뜰 때까지 기다리는 시간
    MOVE_TIMEOUT = 60.0       # 턴테이블 이동 최대 허용 시간

    def can_execute(self, sample_data: dict) -> bool:
        data_keys = set(sample_data.keys())
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        # 서보 키가 있고, 로봇 키는 없을 때
        return has_servo and not has_robot

    def execute(self, sequence_data: list[dict]) -> tuple[bool, str]:
        """
        [두뇌] 시퀀스 데이터를 순차적으로 실행
        Returns: (성공여부, 결과메시지)
        """
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 서보 단독 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 에서 처리될 전체 데이터\n{(sequence_data)}\n", "DEBUG")

        # 처리할 전체 시퀀스 데이터 방송
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        adapter = self.servo
        total_steps = len(sequence_data)
        EVENT_BUS.log.message.emit(f"서보 시퀀스 시작 (총 {total_steps}건)", "INFO")

        try:
            # 1. 초기화 (Setup) - 전원 ON
            for axis_idx in [1, 2, 3]:
                adapter.set_servo_state(axis_idx, True)

            # 2. 실행 루프 (Loop)
            for step_idx, row in enumerate(sequence_data, start=1):

                # (A) 중단 요청 확인
                if self._is_interrupted():
                    adapter.emergency_stop_all()
                    return False, "사용자에 의해 작업이 중단되었습니다."

                # (B) UI 진행률 업데이트
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSING)

                # (C) 명령 생성 및 전송
                # [Axis 1] Tool 공전 (속도 제어)
                pose1 = ServoPoseModel.create_for_axis(row, 'tool_revolution_rpm')
                if pose1.velocity != 0:
                    adapter.move_velocity(1, pose1.velocity)

                # [Axis 2] Tool 자전 (속도 제어)
                pose2 = ServoPoseModel.create_for_axis(row, 'tool_rotation_rpm')
                if pose2.velocity != 0:
                    adapter.move_velocity(2, pose2.velocity)

                # [Axis 3] 턴테이블 (위치 제어)
                pose3 = ServoPoseModel.create_for_axis(row, 'turntable_deg')
                adapter.move_absolute(3, pose3.angle, pose3.velocity)

                # (D) 대기 (Stop-and-Go)
                if not self._wait_for_turntable_completion(3):
                    adapter.emergency_stop_all()

                    # 실패 사유 파악 (중단 vs 타임아웃)
                    msg = "작업 중단됨" if self._is_interrupted else f"턴테이블 응답 없음 또는 시간 초과 ({self.MOVE_TIMEOUT}s)"
                    return False, msg

                # (E) 스텝 완료
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSED)
                time.sleep(0.05) 

            return True, "모든 서보 시퀀스 작업이 완료되었습니다."

        except Exception as e:
            adapter.emergency_stop_all()
            EVENT_BUS.log.message.emit(f"서보 실행 중 오류: {e}", "ERROR")
            return False, f"오류 발생: {str(e)}"

        finally:
            # 3. 종료 처리 (Teardown)
            adapter.emergency_stop_all() # 모든 축 정지
            for axis_idx in [1, 2, 3]:
                adapter.set_servo_state(axis_idx, False) # 전원끄기

    def _wait_for_turntable_completion(self, axis_idx: int) -> bool:
        """
        턴테이블 이동 완료 대기 (Busy Check + Timeout)
        Returns: True(완료), False(실패/중단)
        """
        # -------------------------------------------------------------
        # Phase 1: Busy 신호가 뜰 때까지 대기 (최대 BUSY_WAIT_TIMEOUT 초)
        # -------------------------------------------------------------
        # 명령을 보내자마자 바로 읽으면 아직 Busy가 False일 수 있음
        start_wait = time.time()
        busy_detected = False

        while time.time() - start_wait < self.BUSY_WAIT_TIMEOUT:
            # 중단 요청 체크
            if self._is_interrupted(): return False

            if self.servo.is_busy(axis_idx):
                # Glitch(노이즈)로 인한 판단 착오 방지. Busy가 떴어도 0.1초 더 지켜보고 진짜인지 확인
                time.sleep(0.1)
                if self.servo.is_busy(axis_idx):
                    busy_detected = True
                    break
            # CPU 과점유 방지 - 루프마다 대기
            time.sleep(0.05)

        if not busy_detected:
            EVENT_BUS.log.message.emit(f"축 {axis_idx} 반응 없음 (Busy Timeout)", "ERROR")
            return False

        # -------------------------------------------------------------
        # Phase 2: Busy 신호가 꺼질 때까지 대기 (최대 MOVE_TIMEOUT 초)
        # -------------------------------------------------------------
        move_start_time = time.time()

        # 이동중 - Busy 꺼질 때까지 대기
        #   타임아웃을 길게 잡거나 없애야 함 (이동이 10초 걸릴 수도 있으니까)
        while self.servo.is_busy(axis_idx):
            # 중단 요청 체크
            if self._is_interrupted(): return False

            # 타임아웃 체크 (무한 대기 방지)
            if time.time() - move_start_time > self.MOVE_TIMEOUT:
                EVENT_BUS.log.message.emit(f"축 {axis_idx} 이동 시간 초과 ({self.MOVE_TIMEOUT}초)", "ERROR")
                return False

            # CPU 과점유 방지 - 루프마다 대기
            time.sleep(0.05)
            
        return True

    def _is_interrupted(self) -> bool:
        """
        [안전장치] 현재 스레드 중단 요청 확인
        Walrus operator(:=)를 사용하여 None 체크와 메서드 호출을 한 번에 처리
        """
        # 1. thread 변수에 현재 스레드 할당
        # 2. thread가 None이 아니면(True), 뒤의 isInterruptionRequested() 호출
        # 3. thread가 None이면(False), 바로 False 반환
        return bool((thread := QThread.currentThread()) and thread.isInterruptionRequested())


class IntegratedExecutor(BaseExecutor):
    """
    CSV 파일 형식 (로봇 + 턴테이블 통합 제어)
    """
    def can_execute(self, sample_data: dict) -> bool:
        data_keys = set(sample_data.keys())
        # CSV 통합 키 (polar_coord_...) 가 포함되어 있는지 확인
        #   통합 제어는 로봇과 서보 키가 같이 있다
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        return has_robot and has_servo and ('polar_coord_theta' in data_keys or 'polar_coord_radius' in data_keys)

    def execute(self, sequence_data: list[dict]) -> tuple[bool, str]:
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] CSV 파일 통합 제어 모드로 실행 (데이터 {len(sequence_data)}건)", "INFO")

        # 처리할 전체 시퀀스 데이터 방송
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        # EVENT_BUS.log.message.emit(f"\n\n[{self.__class__.__name__}] 시퀀스:\n{sequence_data}", "DEBUG")



        # --- 다른 위젯 시뮬레이션 용 코드 시작 --- #
        num_sequences = len(sequence_data)
        try:
            for dix, row in enumerate(sequence_data, 1):

                # STOP 버튼 감지 코드
                if (thread := QThread.currentThread()) is not None and thread.isInterruptionRequested():
                    EVENT_BUS.log.message.emit("사용자 요청에 의해 시뮬레이션 중단", "WARNING")
                    # 종료 신호 전송 중 에러가 나더라도, 이미 정지 중이므로 에러를 무시하거나 경고만 남김
                    try:
                        # self.robot은 FanucAdapter
                        self.robot.set_finish_signals()
                    except Exception as e:
                        # 연결이 끊겨서 전송 못 해도 괜찮음 (어차피 멈추는 중)
                        EVENT_BUS.log.message.emit(f"종료 신호 전송 스킵 (연결 없음): {e}", "DEBUG")                        
                        
                    return False, "User Stopped"

                current_id = row.get('id') or dix
                EVENT_BUS.log.message.emit(f"현재 진행중 row: {current_id}", "DEBUG")

                EVENT_BUS.data.progress_updated.emit(current_id, num_sequences, "processing")
                time.sleep(0.5)
                EVENT_BUS.data.progress_updated.emit(current_id, num_sequences, "processed")
            return True, "통합 제어 시뮬레이션 완료"
        except Exception as e:
            return False, f"통합 제어 시뮬레이션 중 에러: {e}"

        """
        # TODO: 이 안의 코드 실제 코드에서도 살려야 된다
        # 실제 운영 코드 예시 (IntegratedExecutor)

                if (thread := QThread.currentThread()) and thread.isInterruptionRequested():
                    EVENT_BUS.log.message.emit("사용자 요청에 의해 작업 중단", "WARNING")
                    
                    try:
                        # 로봇에게 "작업 끝" 알림
                        self.robot.set_finish_signals()
                    except Exception as e:
                        # 실제 운영 시: 에러가 났다는 사실은 로그에 남겨서 나중에 분석할 수 있게 함
                        # 하지만 사용자에게 에러 팝업을 띄우거나 앱을 죽이진 않음
                        EVENT_BUS.log.message.emit(f"종료 신호 전송 실패 (통신 상태 확인 필요): {e}", "WARNING")
                    
                    return False, "User Stopped"
        """


        """
        # 1. 시작 신호
        self.robot.start_sequence_plc_signals()
        # self.servo.start_signal()

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
        data_keys = set(sample_data.keys())
        # TXT 레거시 키 (axis_x, Y...) 와 서보 키가 공존할 때
        has_legacy_robot = any(k in data_keys for k in ['axis_x', 'axis_y', 'axis_z', 'feed_rate'])
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        return has_legacy_robot and has_servo

    def execute(self, sequence_data: list[dict]) -> tuple[bool, str]:
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 레거시 파일 모드로 실행 (데이터 {len(sequence_data)}건)", "INFO")

        # 처리할 전체 시퀀스 데이터 방송
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)        

        return True, "레거시 파일 모드 실행 완료 -> TODO: 로직 만들어야 된다"




# =========================================================
# 3. 게이트웨이 (The Commander)
# =========================================================
class TwinCATCommander:

    def __init__(self, connector: TwinCATConnector):
        self.connector = connector
        
        # 하위 장치 컨트롤러
        self.robot = FanucAdapter(connector)
        self.turntable = ServoAdapter(connector)

        # 등록된 실행기들 (우선순위 순서대로)
        # INTEGRATED(가장 구체적) -> ONLY(일반적) 순으로 배치
        self.executors: List[BaseExecutor] = [
            IntegratedExecutor(self.robot, self.turntable),         # CSV 통합
            LegacyIntegratedExecutor(self.robot, self.turntable),   # TXT 레거시 통합
            FanucOnlyExecutor(self.robot, self.turntable),          # 로봇 단독
            ServoOnlyExecutor(self.robot, self.turntable)           # 서보 단독
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
        print(f"입력된 자료에 맞는 Excutor 선택을 위한 샘플 데이터(sequence_data[0]): {sample_row}")

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


    # ================================= #
    # --- 로봇에게 내리는 명령들 --- #
    # ================================= #
    def apply_user_feed_rate_when_moving_robot(self, feed_rate: float) -> str | None:
        """TargetPositionWidget 에서 사용자가 입력한 Feed Rate 값을 FANUC에 적용"""

        # 로봇이 움직이고 있는지 확인
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

    def are_gagets_busy(self) -> bool:
        """로봇이나 턴테이블 중 하나라도 움직이고 있다면 True(바쁨) 반환"""

        # 로봇 상태 확인
        robot_busy = False
        if self.robot:
            robot_busy = self.robot.read_busy_signal()

        # 턴테이블 상태 확인
        table_busy = False
        if self.turntable:
            table_busy = self.turntable.read_busy_signal()

        # 둘 중 하나라도 바쁘면 시스템은 바쁜 것
        return robot_busy or table_busy

    def start_sequence_plc_signals(self) -> tuple[bool, str]:
        """로봇에게 시작 신호(RSR, Loop 등) 전송"""
        if self.robot:
            try:
                self.robot.set_initial_signals()
                return True, "시작 신호 전송 완료"
            except Exception as e:
                return False, f"시작 신호 전송 실패: {e}"
        return False, "로봇이 연결되지 않았습니다."

    def end_sequence_plc_signals(self) -> tuple[bool, str]:
        """로봇에게 종료/정지 신호 전송"""
        if self.robot:
            try:
                self.robot.set_finish_signals()
                return True, "종료 신호 전송 완료"
            except Exception as e:
                return False, f"종료 신호 전송 실패: {e}"
        return False, "로봇이 연결되지 않았습니다."
