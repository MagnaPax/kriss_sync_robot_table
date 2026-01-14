# communication/twincat_commander.py
"""
TwinCAT Commander (Model Layer)
    전략 패턴(Strategy Pattern) 사용

    역할:
        TwinCAT 에 연결된 기기(FANUC 로봇, 턴테이블) 제어
"""
import time
import threading
from PyQt6.QtCore import QThread, QObject
from abc import ABC, abstractmethod
from typing import List, Any, Optional, Dict

from core.event_bus import EVENT_BUS
from communication.fanuc_adapter import FanucAdapter
from communication.servo_adapter import ServoAdapter
from communication.twincat_connector import TwinCATConnector
from models.fanuc_pose_model import FANUCPose
FanucPoseModel = FANUCPose # Alias for consistency
from models.servo_pose_model import ServoPoseModel
from config.data_formats import (
    TaskStatus, SERVO_KEYS, ROBOT_KEYS,
    KEY_ROBOT_X, KEY_ROBOT_Y, KEY_ROBOT_Z, KEY_ROBOT_W, KEY_ROBOT_P, KEY_ROBOT_R,
    KEY_ROBOT_FEED_RATE, KEY_TURNTABLE_DEG, KEY_TURNTABLE_FEED_RATE,
    KEY_TOOL_REV_RPM, KEY_TOOL_ROT_RPM
)
from models.servo_pose_key import ServoAxis
from models.fanuc_pose_key import FanucSignal
from core.settings import SETTINGS


# =========================================================
# 1. 추상 실행기 (Base Executor)
# =========================================================
class BaseExecutor(ABC):
    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        self.robot = robot
        self.servo = servo

    @abstractmethod
    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        """이 데이터 형식을 처리할 수 있는지 확인"""
        pass

    @abstractmethod
    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """실제 실행 로직"""
        pass


# =========================================================
# 2. 전략 구현 (Strategies)
# =========================================================

class FanucOnlyExecutor(BaseExecutor):
    """로봇 단독 제어"""

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        data_keys = set(sample_data.keys())
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        # 로봇 키가 있고, 서보 키는 없을 때
        return has_robot and not has_servo

    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        FANUC 로봇에게 연속적인 이동 경로를 명령하며 각 스텝마다 정확한 동기화를 보장
        
        1. 초기화:
            - Handshake용 Event와 Callback을 준비
            - `write_initial_signals()`로 로봇을 깨운다
        
        2. 시퀀스 루프 (Step-by-Step):
            a. Delta 계산 (Pre-calculation): 
                - 현재 위치와 목표 위치의 차이(Delta)를 계산한다 (모델 내부 `to_struct`에서 수행).
            b. 패킷 전송 (Trigger): 
                - `write_command_packet()`으로 데이터를 한 방에 보낸다.
            c. 완료 대기 (Handshake):
                - 로봇이 이동을 완료하고 DO45 신호를 Rising Edge(0->1)로 띄울 때까지 기다린다.
                - `_move_complete_event.wait()`로 효율적으로 대기하며, 폴링(무한루프)을 사용하지 않는다.
                - 안전장치: 0.1초마다 `QThread` 중단 요청(Stop 버튼)을 체크하여 즉각 반응한다.
            
        3. 종료:
            - 모든 이동이 끝나면 `set_finish_signals()`로 정리한다.
            - `finally` 블록에서 Notification 리소스를 반드시 해제한다.
        
        Returns:
            (성공여부, 메시지)
        """
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] FANUC 단독 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 에서 처리될 전체 데이터\n{(sequence_data)}\n", "DEBUG")

        # 처리할 전체 시퀀스 데이터 방송
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        adapter = self.robot

        # 사용자 입력 feed rate 초기화 (새 작업 시작이기 때문)
        adapter.override_feed_rate = None

        num_sequences = len(sequence_data)  # 전체 시퀀스 갯수
        
        # Event 객체 생성 (Handshake용)
        # 원본 파일: 260102.FANUC_FULL_THREADING.py
        import threading
        _move_complete_event = threading.Event()
        
        # 콜백 함수 정의
        def _on_robot_move_complete_signal(notification, data):
            # 원본 라인 127: move_next_event.set()
            _move_complete_event.set()

        # 알림(Notification) 등록 핸들
        notify_handle = None

        try:
            # 1. 시작 전 로봇 상태 검증
            adapter.validate_robot_ready()
            
            # Notification 등록
            notify_handle = adapter.register_handshake_callback(_on_robot_move_complete_signal)
            EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] Handshake 알림 등록 완료 (Handle: {notify_handle})", "DEBUG")

            previous_pose = None  # 이전 명령 (Delta 계산용)
            
            # 2. 초기 신호 전송
            # 원본 라인 185: plc.write_by_name(STRUCT_SYMBOL, init_payload, FanucUI1Struct)
            adapter.write_initial_signals()

            # 3. 시퀀스 루프
            for idx, row in enumerate(sequence_data, 1):
                # (A) 중단 요청 확인 (안전장치)
                if (thread := QThread.currentThread()) and thread.isInterruptionRequested():
                    raise InterruptedError("사용자에 의해 작업이 중단되었습니다.")

                adapter.validate_robot_ready() # 매 스텝 시작 전 체크

                # 데이터에 'id'가 있으면 가져오고, 없다면 루프 인덱스(idx)를 id로 사용
                current_id = row.get('id') or idx

                # 현재 시퀀스 진행상태 방송: 진행중
                EVENT_BUS.data.progress_updated.emit(current_id, num_sequences, TaskStatus.PROCESSING)
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 현재 시퀀스 진행상태: {(current_id)}", "DEBUG")

                # 이동 속도 결정
                if adapter.override_feed_rate is not None:
                    # 사용자가 '지금' 바꾼 FEED RATE
                    feed_rate = adapter.override_feed_rate
                else:
                    # GO TO 버튼 눌렀을 때 입력한 FEED RATE 
                    # (또는 데이터에 있는 F값)
                    feed_rate = row.get(KEY_ROBOT_FEED_RATE, 10.0)

                # 4. 목표 포즈 생성 (데이터 매핑)
                target_pose = FANUCPose(
                    x=row.get(KEY_ROBOT_X, 0.0), y=row.get(KEY_ROBOT_Y, 0.0), z=row.get(KEY_ROBOT_Z, 0.0),
                    w=row.get(KEY_ROBOT_W, 0.0), p=row.get(KEY_ROBOT_P, 0.0), r=row.get(KEY_ROBOT_R, 0.0),
                    f=feed_rate
                )
                # 현재 로봇 위치 방송 : 모니터링 워커(PoseMonitorWorker)가 백그라운드에서 방송하고 있다
                EVENT_BUS.log.message.emit(f"\n현재 로봇 위치: {target_pose}\n", "DEBUG")

                # 5. 첫 번째 스텝 처리 (Delta=0)
                if previous_pose is None:
                    # 원본 로직: "if prev_coords is None: move_deltas = zero_deltas.copy()"
                    # to_struct 내부에서 prev_pose와 target_pose가 같으면 Delta 0으로 처리됨
                    # 따라서 첫 번째는 자기 자신을 prev로 넘겨줌
                    previous_pose = target_pose
                
                # 6. 신호(Signal) 준비
                # 원본 라인 177: base_signals = {'IMSP': True, ...}
                signals = {
                    'IMSP': True, 'Hold': True, 'SFSP': True, 'Enable': True,
                    'CycleStop': False, 'Start': False, 'RSR2': False, 'DI43': True # DI43=True (이동 명령)
                }
                
                # 원본 라인 208: if i == 1: signals['RSR2'] = True
                # (첫 번째 무브먼트일 때 RSR2를 켜주는 로직 복원)
                if idx == 1:
                    signals['RSR2'] = True

                # 7. 패킷 생성 (Delta 계산은 모델 내부 위임)
                # 원본 라인 210: payload = pack_fanuc_payload(...)
                packet = target_pose.to_struct(previous_pose, signals)

                # 8. 전송 (Write)
                # 원본 라인 213: plc.write_by_name(STRUCT_SYMBOL, payload, FanucUI1Struct)
                adapter.write_command_packet(packet)
                
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] #{idx} 명령 전송 완료. Rising Edge 대기 중...", "DEBUG")
                
                # 9. Handshake 대기 (Wait for Rising Edge)
                # 원본 라인 219: if move_next_event.wait(timeout=20.0): ...
                # QThread 중단을 감지하기 위해 루프 사용 (사용자 요청 시 즉시 반응)
                
                _move_complete_event.clear() # 확실하게 클리어
                
                wait_start = time.time()
                timeout = 20.0 # 20초 타임아웃
                success = False
                
                while time.time() - wait_start < timeout:
                    # (A) 중단 요청 확인
                    if (thread := QThread.currentThread()) and thread.isInterruptionRequested():
                        EVENT_BUS.log.message.emit("대기 중 사용자 중단 요청 감지", "WARNING")
                        raise InterruptedError("사용자에 의해 작업이 중단되었습니다.")
                    
                    # (B) 이벤트 확인 (0.1초씩 끊어서 대기)
                    if _move_complete_event.wait(timeout=0.1):
                        success = True
                        break
                        
                if not success:
                    # 타임아웃인지 중단인지 확인
                    if (thread := QThread.currentThread()) and thread.isInterruptionRequested():
                        raise InterruptedError("사용자에 의해 작업이 중단되었습니다.")
                    else:
                        raise TimeoutError(f"[{self.__class__.__name__}] 로봇 응답 시간 초과 (Timeout 20s)")
                
                EVENT_BUS.log.message.emit(" -> OK (Rising Edge Detected)", "DEBUG")

                # 10. 기준점 업데이트
                # 원본 라인 226: prev_coords = target_coords
                previous_pose = target_pose

                # 11. 첫 번째 스텝 이후 RSR2 끄기 (옵션)
                # 원본 라인 228: if i == 1: signals['RSR2'] = False ...
                if idx == 1:
                    signals['RSR2'] = False
                    # 신호만 끄고 다시 전송 (Delta는 그대로 둬야 함? 원본은 그대로 둠)
                    # 원본은 target_coords, move_deltas 그대로 사용
                    packet = target_pose.to_struct(previous_pose, signals) # previous_pose가 갱신되었으므로 Delta는 0이 됨
                    adapter.write_command_packet(packet)


                # 현재 시퀀스 진행상태 방송: 완료
                EVENT_BUS.data.progress_updated.emit(current_id, num_sequences, TaskStatus.COMPLETED)

            # 3. 종료 신호
            # 원본의 finally 블록 혹은 루프 종료 후 정리
            adapter.set_finish_signals()
            return True, "작업 완료"
        
        except InterruptedError as e:
            EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 작업이 사용자에 의해 중단되었습니다. 로봇 정지 신호 전송...", "WARNING")
            try:
                adapter.set_emergency_stop() # 명시적 정지 신호
            except Exception as stop_err:
                EVENT_BUS.log.message.emit(f"정지 신호 전송 실패: {stop_err}", "ERROR")
            return False, str(e)


        except Exception as e:
            EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 예외 발생. 로봇 정지 시도...", "ERROR")
            try:
                adapter.set_emergency_stop()
            except:
                pass
            
            # 사용자 친화적 메시지 변환
            msg = str(e)
            if "Robot Fault" in msg:
                msg = "로봇 하드웨어 결함이 감지되었습니다. 비상 정지 버튼이 눌려있거나 컨트롤러에 알람이 있는지 확인 후 리셋해 주세요."
            elif "symbol not found" in msg.lower():
                msg = "로봇 통신 변수를 찾을 수 없습니다. PLC 프로그램이 실행 중인지 확인해 주세요."

            return False, f"[{self.__class__.__name__}] {msg}"
            
        finally:
            # 시퀀스 실행 종료 방송
            EVENT_BUS.data.sequence_job_finished.emit()

            # 리소스 정리 (콜백 해제)
            if notify_handle is not None:
                adapter.remove_notification(notify_handle)
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 계산 요청 알림 해제 완료", "DEBUG")

    def _is_interrupted(self) -> bool:
        """안전장치: 현재 실행 중인 스레드가 정지 요청을 받았는지 확인한다."""
        return bool((thread := QThread.currentThread()) and thread.isInterruptionRequested())

class ServoOnlyExecutor(BaseExecutor):
    """
    [서보 모터 전용 실행기]
    로봇 없이 Panasonic 서보 모터 3축(툴 2개 + 턴테이블 1개)만 단독 제어
    """

    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        super().__init__(robot, servo)
        
        # 서보를 기다려주는 시간 (설정 파일에서 값 로드)
        self.BUSY_TIMEOUT = SETTINGS.servo.busy_timeout
        self.MOVE_TIMEOUT = SETTINGS.servo.move_timeout

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        data_keys = set(sample_data.keys())
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        # 서보 키가 있고, 로봇 키는 없을 때
        return has_servo and not has_robot

    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        [두뇌] 시퀀스 데이터를 순차적으로 실행
        Returns: (성공여부, 결과메시지)
        """
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 서보 단독 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 에서 처리될 전체 데이터\n{(sequence_data)}\n", "DEBUG")

        # 처리할 전체 시퀀스 데이터 방송
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        # 설정값 최신화 (실행 시점의 Settings 값 적용)
        self.BUSY_TIMEOUT = SETTINGS.servo.busy_timeout
        self.MOVE_TIMEOUT = SETTINGS.servo.move_timeout

        adapter = self.servo
        total_steps = len(sequence_data)
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 서보 시퀀스 시작 (총 {total_steps}건)", "INFO")
        
        # 1. 초기화 (Setup) - 전원 ON
        for axis in ServoAxis:
            adapter.set_servo_state(axis, True)
            # [SAFETY CHECK] 실행 전 서보 에러 확인
            if adapter.has_servo_error(axis):
                raise RuntimeError(f"서보 축({axis.name})에 에러가 감지되었습니다. 작업을 중단합니다.")

        try:
            # 2. 실행 루프 (Loop)
            for step_idx, row in enumerate(sequence_data, start=1):

                # (A) 중단 요청 확인
                if self._is_interrupted():
                    raise InterruptedError("사용자에 의해 작업이 중단되었습니다.")

                # (B) UI 진행률 업데이트
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSING)
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] {step_idx}/{total_steps} 진행 중", "DEBUG")

                # (Pre-Check) 턴테이블 이동 결정
                pose_turntable = ServoPoseModel.create_for_axis(row, KEY_TURNTABLE_DEG)
                current_turntable_pos = adapter.read_current_servo_motion(ServoAxis.TURNTABLE)['position']
                
                should_move_turntable = True

                # 1. 위치 체크: 이미 목표 위치에 있는가?
                if abs(current_turntable_pos - pose_turntable.angle) < 0.05:
                    EVENT_BUS.log.message.emit(
                        f"[{self.__class__.__name__}] 턴테이블이 이미 목표 각도({pose_turntable.angle:.2f}°)에 있습니다. 이동 스킵.",
                        "INFO"
                    )
                    should_move_turntable = False

                # 2. 속도 체크: 속도가 0인가?
                elif pose_turntable.velocity <= 0:
                    EVENT_BUS.log.message.emit(
                        f"[{self.__class__.__name__}] 턴테이블 속도가 0입니다. 이동 스킵.",
                        "INFO"
                    )
                    should_move_turntable = False

                # (C) 명령 생성 및 전송
                seq_id = row.get('id', step_idx)
                # 보기 좋게 주요 파라미터만 추출하여 로그 출력
                log_msg = (
                    f"\n"
                    f"[{self.__class__.__name__}] 시퀀스 #{seq_id} 실행 시작 ({step_idx}/{total_steps}) | "
                    f"공전={row.get(KEY_TOOL_REV_RPM, 0):.1f}RPM, "
                    f"자전={row.get(KEY_TOOL_ROT_RPM, 0):.1f}RPM, "
                    f"턴테이블={row.get(KEY_TURNTABLE_DEG, 0):.1f}deg, "
                    f"턴테이블 속도={row.get(KEY_TURNTABLE_FEED_RATE, 0):.1f}mm/rev"
                )
                EVENT_BUS.log.message.emit(log_msg, "INFO")

                # [Axis 1] Tool 공전 (속도 제어)
                if KEY_TOOL_REV_RPM in row:
                    pose_revolution = ServoPoseModel.create_for_axis(row, KEY_TOOL_REV_RPM)
                    EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] pose_revolution 생성: {pose_revolution}", "DEBUG")
                    if pose_revolution.velocity != 0:
                        adapter.move_velocity(ServoAxis.TOOL_REVOLUTION, pose_revolution.velocity)
                    else:
                        adapter.stop_axis(ServoAxis.TOOL_REVOLUTION)

                    # 명령 후 즉시 에러 체크
                    err_rev = adapter.is_servo_error_active(ServoAxis.TOOL_REVOLUTION)
                    if err_rev['error']:
                        EVENT_BUS.log.message.emit(f"Axis 1 에러 발생! ID: {err_rev['id']}", "ERROR")

                # [Axis 2] Tool 자전 (속도 제어)
                if KEY_TOOL_ROT_RPM in row:
                    pose_rotation = ServoPoseModel.create_for_axis(row, KEY_TOOL_ROT_RPM)
                    EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] pose_rotation 생성: {pose_rotation}", "DEBUG")
                    if pose_rotation.velocity != 0:
                        adapter.move_velocity(ServoAxis.TOOL_ROTATION, pose_rotation.velocity)
                    else:
                        adapter.stop_axis(ServoAxis.TOOL_ROTATION)

                    # 명령 후 즉시 에러 체크
                    err_rot = adapter.is_servo_error_active(ServoAxis.TOOL_ROTATION)
                    if err_rot['error']:
                        EVENT_BUS.log.message.emit(f"Axis 2 에러 발생! ID: {err_rot['id']}", "ERROR")

                # [Axis 3] 턴테이블 (위치 제어)
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] pose_turntable 생성: {pose_turntable}", "DEBUG")
                if should_move_turntable:
                    adapter.move_turntable_atomic(ServoAxis.TURNTABLE, pose_turntable.angle, pose_turntable.velocity)

                # (D) 대기 (Stop-and-Go)
                # 각 스텝의 이동이 완료될 때까지 대기 (Stop-and-Go 방식)
                # 단, 이동 명령을 내린 경우에만 대기함
                if should_move_turntable:
                    if not self._wait_for_turntable_completion(ServoAxis.TURNTABLE, target_pos=pose_turntable.angle):
                        adapter.request_immediate_stop()

                        # 실패 사유 파악 (중단 vs 타임아웃)
                        msg = "작업 중단됨" if self._is_interrupted() else f"턴테이블 응답 없음 또는 시간 초과 ({self.MOVE_TIMEOUT}s)"
                        return False, msg

                # 개발용 로그
                feedback_revolution = adapter.read_current_servo_motion(ServoAxis.TOOL_REVOLUTION)
                feedback_rotation = adapter.read_current_servo_motion(ServoAxis.TOOL_ROTATION)
                feedback_turntable = adapter.read_current_servo_motion(ServoAxis.TURNTABLE)

                if KEY_TOOL_REV_RPM in row:
                    EVENT_BUS.log.message.emit(
                        f"[{self.__class__.__name__}] 툴 공전 (RPM) 완료: 목표={pose_revolution.velocity:.1f}, 현재={feedback_revolution['velocity']:.1f}", "DEBUG"
                    )
                if KEY_TOOL_ROT_RPM in row:
                    EVENT_BUS.log.message.emit(
                        f"[{self.__class__.__name__}] 툴 자전 (RPM) 완료: 목표={pose_rotation.velocity:.1f}, 현재={feedback_rotation['velocity']:.1f}", "DEBUG"
                    )
                EVENT_BUS.log.message.emit(
                    f"[{self.__class__.__name__}] 턴테이블 (deg & RPM) 완료: 목표={pose_turntable.angle:.1f} & {pose_turntable.velocity:.1f}, 현재={feedback_turntable['position']:.1f} & {feedback_turntable['velocity']:.1f}", "DEBUG"
                )

                # (E) 스텝 완료 방송
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.COMPLETED)

            return True, "모든 서보 시퀀스 작업이 완료되었습니다."

        except InterruptedError as e:
            EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 작업이 사용자에 의해 중단되었습니다. 서보 정지 신호 전송...", "WARNING")
            adapter.request_immediate_stop()
            return False, str(e)

        except Exception as e:
            try:
                adapter.request_immediate_stop()
            except Exception:
                pass # 에러 처리 중 발생한 에러는 무시(원래 발생한 에러가 더 중요함)
                
            return False, f"[{self.__class__.__name__}] 오류 발생: {str(e)}"

        finally:
            # 시퀀스 실행 종료 방송
            EVENT_BUS.data.sequence_job_finished.emit()

            # 3. 종료 처리 (Teardown)
            EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 종료 절차: 서보모터 정지 및 전원 차단을 시도합니다...", "DEBUG")

            # MOVE_TIMEOUT을 통해 충분한 감속시간 확보
            is_safely_shutdown = adapter.shutdown_all_with_power_off(timeout=self.MOVE_TIMEOUT)

            if is_safely_shutdown:
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 모든 서보모터가 안전하게 종료되었습니다. ", "INFO")
            else:
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 경고: 정지 대기 시간 초과({self.MOVE_TIMEOUT}s). 되었거나 종료 절차 중 오류가 발생하였습니다.", "WARNING")


    def _wait_for_turntable_completion(self, axis_idx: int, target_pos: Optional[float] = None) -> bool:
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] {axis_idx}축 이동 완료 대기 중...", "DEBUG")
        """
        턴테이블 이동 완료 대기 (Busy Check + Timeout)
        Returns: True(완료), False(실패/중단)
        """
        try:
            # -------------------------------------------------------------
            # Phase 1: Busy 신호가 뜰 때까지 대기 (최대 BUSY_TIMEOUT 초)
            # -------------------------------------------------------------
            # 명령을 보내자마자 바로 읽으면 아직 Busy가 False일 수 있음
            start_wait = time.time()
            busy_detected = False

            while time.time() - start_wait < self.BUSY_TIMEOUT:
                
                # (A) 움직임 여부 체크 (속도 기준)
                moving = self.servo.is_servo_moving_physically(axis_idx)
                
                if moving:
                    busy_detected = True
                    EVENT_BUS.data.servo_physical_moving_status_changed({'is_servo_moving': True})
                else:
                    # 이미 목표 위치 부근이라면, 이동 명령이 무시된(No-op) 것으로 간주하고 성공 반환
                    if target_pos is not None:
                        current_pos = self.servo.read_current_servo_motion(axis_idx)['position']
                        if abs(current_pos - target_pos) < 0.05: # 0.05도 오차 허용
                            EVENT_BUS.log.message.emit(
                                f"[{self.__class__.__name__}] 축 {axis_idx}가 이미 목표 위치({target_pos:.3f})에 있으므로 대기를 종료합니다.", 
                                "DEBUG"
                            )
                            return True
                
                # (B) 움직임이 감지된 이후 -> 멈출 때까지 대기
                if busy_detected and not moving:
                    # 움직이다가 멈췄으면 -> 완료 확인
                    feedback = self.servo.read_current_servo_motion(axis_idx)
                    actual_pos = feedback['position']
                    EVENT_BUS.log.message.emit(
                        f"[{self.__class__.__name__}] Axis {axis_idx} 이동 완료: CSV목표={target_pos:.3f}, 현재위치={actual_pos:.3f}", 
                        "DEBUG"
                    )
                    return True

                # (C) 시퀀스 완전 종료 체크 (PLC 쪽에서 강제 종료 시)
                if self._is_interrupted():
                    return False

                time.sleep(0.1)
            
            # 만약 루프가 종료됐고 바쁨이 여전히 감지되지 않았다면 바쁨 신호가 제대로 전달되지 않았다는 의미
            if not busy_detected:
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 축 {axis_idx} 반응 없음 (Busy Timeout)", "ERROR")
                return False

            # -------------------------------------------------------------
            # Phase 2: 멈출 때까지 대기 (최대 MOVE_TIMEOUT 초)
            # -------------------------------------------------------------
            move_start_time = time.time()

            # 이동중 - 멈출 때까지 대기
            #   타임아웃을 길게 잡거나 없애야 함 (이동이 10초 걸릴 수도 있으니까)
            while self.servo.is_servo_moving_physically(axis_idx):
                # 중단 요청 체크
                if self._is_interrupted(): return False

                # 타임아웃 체크 (무한 대기 방지)
                if time.time() - move_start_time > self.MOVE_TIMEOUT:
                    EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 축 {axis_idx} 이동 시간 초과 ({self.MOVE_TIMEOUT}초)", "ERROR")
                    return False

            feedback = self.servo.read_current_servo_motion(axis_idx)
            actual_pos = feedback['position']
            EVENT_BUS.log.message.emit(
                f"[{self.__class__.__name__}] Axis {axis_idx} 이동 완료: CSV목표={target_pos:.3f}, 현재위치={actual_pos:.3f}", 
                "DEBUG"
            )
            return True
        
        finally:
            # 성공/실패 여부에 상관없이 마지막에는 바쁨 신호를 해제
            EVENT_BUS.data.servo_physical_moving_status_changed({'is_servo_moving': False})

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
    """CSV 파일 형식 (로봇 + 턴테이블 통합 제어)"""

    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        super().__init__(robot, servo)
        
        # 서보를 기다려주는 시간 (설정 파일에서 값 로드)
        self.BUSY_TIMEOUT = SETTINGS.servo.busy_timeout
        self.MOVE_TIMEOUT = SETTINGS.servo.move_timeout

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        data_keys = set(sample_data.keys())
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        has_specific_key = (KEY_TURNTABLE_DEG in data_keys) or (KEY_ROBOT_X in data_keys)
        return has_robot and has_servo and has_specific_key

    def _calculate_and_pack(
        self, 
        current_robot_pose: FanucPoseModel, 
        target_robot_pose: FanucPoseModel, 
        current_turntable_angle: float,
        target_turntable_angle: float,
        target_turntable_velocity: float,
        previous_robot_velocity: float, 
        data_ready: bool, 
        start_trigger: bool
    ) -> tuple[Any, float]:
        """
        [Helper] 로봇 속도 계산 및 데이터 패킷 생성
        턴테이블 이동 시간을 기준으로 로봇 속도를 동기화 계산함.
        """
        # 1. 턴테이블 이동 시간 계산
        tt_delta = abs(target_turntable_angle - current_turntable_angle)
        expected_move_time = tt_delta / target_turntable_velocity if target_turntable_velocity > 0 else 0.0
        
        # 2. 로봇 이동 거리 계산
        robot_dist, _ = current_robot_pose.distance_to(target_robot_pose)
        
        # 3. 로봇 속도 역산 (v = d / t)
        if robot_dist < 0.001: 
            robot_calculated_velocity = 0.0
        elif expected_move_time < 0.001:
            # 시간이 0에 가까우면 (턴테이블 이동 없음) 이전 속도 유지하거나 기본값
            robot_calculated_velocity = previous_robot_velocity if previous_robot_velocity > 0 else 100.0
        else:
            robot_calculated_velocity = robot_dist / expected_move_time
            
        # 안전 제한 (Max 500 mm/s)
        robot_calculated_velocity = min(robot_calculated_velocity, 500.0)
        
        # 4. 최종 타겟 포즈 (속도 포함)
        robot_target_final = FanucPoseModel(
            x=target_robot_pose.x, y=target_robot_pose.y, z=target_robot_pose.z,
            w=target_robot_pose.w, p=target_robot_pose.p, r=target_robot_pose.r,
            f=robot_calculated_velocity
        )
        
        # 5. 신호 조합
        signals = {
            FanucSignal.IMSP: True, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
            FanucSignal.CYCLE_STOP: False, FanucSignal.START: False, 
            FanucSignal.RSR2: False,       # [CHANGE] No RSR2
            FanucSignal.RSR3: True,        # [CHANGE] Use RSR3 (Consistent with 260108)
            FanucSignal.DATA_READY_DI43: data_ready,   # [DATA READY]
            FanucSignal.SYNC_START_TRIGGER_DI44: start_trigger # [TRIGGER]
        }
        
        # 6. 패킷 생성
        packet = robot_target_final.to_struct(current_robot_pose, signals)
        return packet, robot_calculated_velocity

    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] CSV 통합 동기화 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")

        robot = self.robot
        servo = self.servo
        
        # =========================================================================
        # 1. 동기화 이벤트 객체 생성
        # =========================================================================
        # 역할: 비동기 -> 동기 변환
        # PLC 통신은 본질적으로 비동기이다. 즉, 로봇이 언제 도착할지 모른다.
        # 반면 Python의 제어 루프는 순차적으로 실행되어야 한다.
        # 이 두 세계를 연결하기 위해 'Threading Event'를 사용한다.
        # - 동작: Main Thread는 event.wait()로 멈춰 있고, Callback Thread가 event.set()으로 깨워준다
        calculation_request_event = threading.Event()   # 로봇: "다음 데이터 주세요" (DO45)
        robot_motion_done_event = threading.Event()     # 로봇: "이동 끝났어요" (DO46)
        motor_motion_done_event = threading.Event()     # 턴테이블: "회전 끝났어요" (Servo Done)
        
        self._timestamp_turntable_done = None
        self._timestamp_robot_done = None
        
        # =========================================================================
        # 2. 콜백 함수 정의
        # =========================================================================
        # 역할: C++ Level -> Python Level 신호 전달
        # ADS/CTYPES 라이브러리는 백그라운드 스레드에서 PLC 신호를 감시하다가 변화가 생기면 이 함수들을 호출한다
        # 이곳에서 복잡한 로직을 수행하면 절대 안 됨 (데드락 위험)
        # 단순히 깃발(Event)만 흔들어주고 빨리 리턴해야 된다
        def _on_calculation_request(n, d): 
            calculation_request_event.set()
        def _on_robot_motion_done(n, d): 
            self._timestamp_robot_done = time.time()
            robot_motion_done_event.set()
        def _on_turntable_motion_done(n, d):
            self._timestamp_turntable_done = time.time()
            motor_motion_done_event.set()

        # =========================================================================
        # 3. 알림 구독
        # =========================================================================
        # Polling vs Interrupt
        # 일정 시간마다 주기적으로 도착했는지 계속 물어보는 것(Polling)은 CPU 낭비가 심하고 반응이 느리다.
        # "도착하면 알려줘!" 라고 등록(Subscribe)해두면 PLC가 신호를 보낼 때 즉시 반응할 수 있다.
        # 반환된 handle은 나중에 연결을 끊을 때 사용한다.
        handle_calc = robot.register_calculation_request_callback(_on_calculation_request)
        handle_motion = robot.register_robot_motion_done_callback(_on_robot_motion_done)
        handle_turntable = servo.register_turntable_motion_done_callback(_on_turntable_motion_done)

        try:
            # 초기화
            for axis in ServoAxis:
                servo.set_servo_state(axis, True)
                # [SAFETY CHECK] 실행 전 서보 에러 확인
                if servo.has_servo_error(axis):
                    raise RuntimeError(f"서보 축({axis.name})에 에러가 감지되었습니다. 작업을 중단합니다.")

            # [SAFETY CHECK] 로봇 에러 확인
            robot.validate_robot_ready()
            
            # 상태 변수
            current_pose = FanucPoseModel(x=0, y=0, z=0, w=0, p=0, r=0)
            previous_robot_velocity = 0.0
            
            # 턴테이블 초기 각도 읽기 (안전)
            try:
                tt_fb = servo.read_current_servo_motion(ServoAxis.TURNTABLE)
                current_turntable_angle = tt_fb['position']
            except:
                current_turntable_angle = 0.0
            
            prev_motor_active = False # [Optimization]
            total_steps = len(sequence_data)
            
            # =========================================================================
            # [Step 1: Immediate Start]
            # =========================================================================
            if sequence_data:
                row = sequence_data[0]
                EVENT_BUS.data.progress_updated.emit(1, total_steps, TaskStatus.PROCESSING)

                # -----------------------------------------------------------------
                # 1. Start Motor (3축 동시 제어)
                # -----------------------------------------------------------------
                # 첫 번째 스텝은 로봇과의 핸드셰이크(Handshake) 없이 즉시 시작한다
                # 로봇이 이미 초기 위치에 도착해 있다고 가정하거나
                # 첫 이동은 별도의 트리거 없이 RSR 신호만으로 시작하기 때문
                
                # (A) 데이터 파싱 (Parse Data)
                target_pose = FanucPoseModel.from_dict(row)
                pose_turntable = ServoPoseModel.create_for_axis(row, KEY_TURNTABLE_DEG)
                rpm_rev = row.get(KEY_TOOL_REV_RPM, 0.0)
                rpm_rot = row.get(KEY_TOOL_ROT_RPM, 0.0)
                
                # (B) 모터 이동 여부 판단 (Optimization)
                # 이번 스텝에서 턴테이블이 움직이는지 미리 체크하여
                # 다음 스텝(Step 2)에서 '모터 완료 대기'를 할지 말지 결정
                if abs(pose_turntable.angle - current_turntable_angle) > 0.05:
                    prev_motor_active = True
                else:
                    prev_motor_active = False

                # (C) 로봇 데이터 전송
                # Step 1: (260108) 로직 반영 - DI44 트리거를 포함하여 시작
                packet, velocity = self._calculate_and_pack(
                    current_pose, target_pose, 
                    current_turntable_angle, pose_turntable.angle, pose_turntable.velocity,
                    0.0, 
                    data_ready=True,    # -> DI43 (Loop On)
                    start_trigger=True  # -> DI44 (Start Trigger On)
                )
                robot.write_command_packet(packet)
                
                # (D) 펄스 리셋 (Trig bit Off)
                # DI44 펄스 리셋 (Rising Edge를 위해 즉시 끔)
                robot.write_digital_signal(FanucSignal.SYNC_START_TRIGGER_DI44, False)

                # 2. Start Motor (동기화 됨)
                servo.execute_synchronized_motion(
                    turntable_moving_velocity=pose_turntable.velocity, 
                    turntable_target_position=pose_turntable.angle, 
                    spindle_rotation_velocity=rpm_rot, 
                    spindle_revolution_velocity=rpm_rev
                )
                EVENT_BUS.log.message.emit("[Init] Step 1 Started (DI44 Triggered).", "DEBUG")
                
                # Update State
                current_pose = target_pose
                current_turntable_angle = pose_turntable.angle
            # =========================================================================
            # [Step 2+: Pipeline Loop]
            # =========================================================================
            # 이 루프는 [PLC와 Python간의 4단계 핸드셰이크]를 통해 정밀하게 동기화 된다
            #
            # [원리: Pipeline Architecture]
            # 1. Wait Calc Request (DO45): PLC가 "다음 데이터 내놔" 할 때까지 대기
            # 2. Pre-load Data: 다음 로봇/모터 좌표를 미리 계산해서 쓰기 (DI43=True, DI44=False)
            # 3. Wait Previous Done (DO46): 이전 동작이 '완전히' 끝날 때까지 대기 (Main Motion Done)
            # 4. Trigger (DI44=True): 동시에 출발! (Hand-in-hand)
            # =================================================================
            for i in range(1, total_steps):
                step_idx = i + 1
                row = sequence_data[i]

                # -----------------------------------------------------------------
                # 1. DO45 신호 대기 (Notification으로 받은 이벤트 wait)
                # -----------------------------------------------------------------
                # 로봇이 현재 동작을 수행하는 도중에, "다음 동작을 미리 준비해달라"고 요청을 보낸다.
                # 이 신호를 받으면 다음 스텝의 좌표를 계산해서 미리 메모리에 써둬야 한다
                if not self._wait_event_with_safety(calculation_request_event, timeout=self.BUSY_TIMEOUT):
                    if self._is_interrupted(): raise InterruptedError("사용자에 의해 작업이 중단되었습니다.")
                    raise TimeoutError(f"Step {step_idx}: DO45 (Calculation Request) Timeout")
                calculation_request_event.clear()

                # -----------------------------------------------------------------
                # 2. Pre-load (데이터 미리 채우기)
                # -----------------------------------------------------------------
                # PLC 메모리(UI1 구조체)에 다음 좌표와 속도를 기록한다
                # 아직 '출발(StartTrigger)' 신호는 주지 않는다 (DI44=False)
                # 단지 '데이터가 준비되었다(DataReady)' 신호만 준다 (DI43=True)
                target_pose = FanucPoseModel.from_dict(row)
                pose_turntable = ServoPoseModel.create_for_axis(row, KEY_TURNTABLE_DEG)
                
                packet, velocity = self._calculate_and_pack(
                    current_pose, target_pose, 
                    current_turntable_angle, pose_turntable.angle, pose_turntable.velocity,
                    previous_robot_velocity, 
                    data_ready=True,    # -> DI43 (계속 Loop)
                    start_trigger=False # -> DI44 (아직 대기)
                )
                robot.write_command_packet(packet)
                EVENT_BUS.log.message.emit(f"[Step {step_idx}] 데이터 미리 전송 완료 (Pre-loaded)", "DEBUG")

                # -----------------------------------------------------------------
                # 3. Wait Previous Robot step done (DO46: 이전 동작 완료 대기)
                # -----------------------------------------------------------------
                # 로봇이 이전 목표 지점에 '물리적으로' 도착했는지 확인한다
                # 도착하지 않았다면 다음 명령을 바로 내리면 안 된다. (충돌 방지)
                robot_motion_done_event.clear()
                motor_motion_done_event.clear() # 모터 완료 이벤트도 초기화
                self._timestamp_turntable_done = None 
                
                if not self._wait_event_with_safety(robot_motion_done_event, timeout=self.MOVE_TIMEOUT):
                    if self._is_interrupted(): raise InterruptedError("사용자에 의해 작업이 중단되었습니다.")
                    raise TimeoutError(f"[Step {step_idx}] 로봇 이동 완료 대기 시간 초과 (DO46)")
                
                # -----------------------------------------------------------------
                # 4. Wait Motor (Optimization: 모터 완료 대기)
                # -----------------------------------------------------------------
                # [스마트 동기화]
                # 만약 이전 스텝에서 모터(턴테이블)가 움직였다면, 모터도 다 돌았는지 확인해야 한다
                # 로봇만 도착하고 모터는 아직 돌고 있는데 다음 명령을 내리면 축이 꼬인다
                if prev_motor_active:
                    # 모터가 움직였던 경우에만 대기 (안 움직였으면 즉시 통과 -> 시간 절약)
                    if not self._wait_event_with_safety(motor_motion_done_event, timeout=self.MOVE_TIMEOUT):
                        # 타임아웃 발생 시, 동기화가 깨진 것으로 간주하고 멈춘다
                        if self._is_interrupted(): raise InterruptedError("사용자에 의해 작업이 중단되었습니다.")
                        raise TimeoutError(f"[Step {step_idx}] 턴테이블 이동 완료 대기 시간 초과")
                
                    # (디버깅용) 로봇과 턴테이블의 도착 시간 차이를 로그에 남김
                    if self._timestamp_robot_done and self._timestamp_turntable_done:
                        diff = (self._timestamp_turntable_done - self._timestamp_robot_done) * 1000
                        EVENT_BUS.log.message.emit(f"동기화 오차 확인: {diff:.1f}ms", "DEBUG")
                
                # 이전 스텝이 완전히 끝났다는 방송 송출
                EVENT_BUS.data.progress_updated.emit(i, total_steps, TaskStatus.COMPLETED)
                # 다음 스텝이 '진행 중' 상태로 진입했다는 방송 송출
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSING)

                # -----------------------------------------------------------------
                # 5. Trigger Next or Finish (Loop Termination Logic)
                # -----------------------------------------------------------------
                # (260108) 로봇 팀 요구사항:
                # 마지막 스텝에서는 'Trigger(DI44)'를 보내지 않고, 'DI43(Data Loop)'를 꺼서
                # 로봇이 루프를 빠져나오게 한다.

                if step_idx == total_steps:
                    # (1) 마지막 스텝 감지 -> DI43 끔 (Loop Exit)
                    EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 마지막 스텝 감지: 루프 탈출 신호 전송 (DI43=False)", "INFO")
                    
                    # (A) 모터 이동 (Last Move)
                    servo.move_turntable_atomic(ServoAxis.TURNTABLE, pose_turntable.angle, pose_turntable.velocity)
                    
                    # (B) 로봇 루프 탈출 신호 (DI43 OFF)
                    robot.write_digital_signal(FanucSignal.DATA_READY_DI43, False)
                    
                    # (C) 루프 즉시 종료
                    # 더 이상 Trigger(DI44)를 보내지 않고 루프 탈출
                    EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.COMPLETED)   # 완료 방송
                    break 

                else:
                    # [Normal Trigger Sequence]
                    
                    # (A) 이번 스텝에서 모터가 움직여야 하는지 미리 계산 (다음 루프의 'Sync Check'를 위해)
                    if abs(pose_turntable.angle - current_turntable_angle) > 0.05:
                        prev_motor_active = True
                    else:
                        prev_motor_active = False # 움직임이 미미하면 안 움직인 것으로 간주 (Wait Motor 스킵)
                    
                    # (B) 로봇에게 트리거 전송 (DI44=True가 포함된 패킷)
                    packet_trig, _ = self._calculate_and_pack(
                        current_pose, target_pose, 
                        current_turntable_angle, pose_turntable.angle, pose_turntable.velocity,
                        previous_robot_velocity, 
                        data_ready=True, start_trigger=True
                    )
                    robot.write_command_packet(packet_trig)
                    
                    # (C) 턴테이블에게 트리거 전송 (Atomic Write)
                    servo.move_turntable_atomic(ServoAxis.TURNTABLE, pose_turntable.angle, pose_turntable.velocity)
                    
                    # (D) 펄스 리셋 (Trig bit Off)
                    # 트리거는 펄스 형태여야 하므로, 켜자마자 바로 꺼준다. (Rising Edge 감지용)
                    robot.write_digital_signal(FanucSignal.SYNC_START_TRIGGER_DI44, False)
                    
                    EVENT_BUS.log.message.emit(f" -> [Step {step_idx}] 동시 출발 트리거 완료", "DEBUG")
                    
                    # (E) 현재 위치 정보 갱신 (다음 계산을 위해)
                    current_pose = target_pose
                    current_turntable_angle = pose_turntable.angle
                    previous_robot_velocity = velocity

            # 모든 스텝이 완료되었다는 방송 송출
            EVENT_BUS.data.progress_updated.emit(total_steps, total_steps, TaskStatus.COMPLETED)
            # [Loop End] 모든 시퀀스 수행 완료
            return True, "작업 완료"

        except InterruptedError as e:
            EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 작업이 사용자에 의해 중단되었습니다. 장비 정지 신호 전송...", "WARNING")
            
            # 1. 로봇 비상 정지 (IMSP, CycleStop)
            try:
                robot.set_emergency_stop()
            except Exception as r_err:
                EVENT_BUS.log.message.emit(f"로봇 정지 명령 실패: {r_err}", "ERROR")

            # 2. 로봇 트리거 리셋 (혹시 켜져 있을 경우)
            try:
                robot.write_digital_signal(FanucSignal.SYNC_START_TRIGGER_DI44, False)
            except: pass

            # 3. 서보 비상 정지 (Stop All)
            try:
                servo.request_immediate_stop()
            except Exception as s_err:
                EVENT_BUS.log.message.emit(f"서보 정지 명령 실패: {s_err}", "ERROR")

            return False, str(e)

        except Exception as e:
            EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 예외 발생. 장비 정지 시도...", "ERROR")
            
            # 예외 발생 시에도 안전을 위해 정지 시도
            try: robot.set_emergency_stop() 
            except: pass
            try: servo.request_immediate_stop() 
            except: pass

            return False, f"오류 발생: {e}"
            
        finally:
            # -----------------------------------------------------------------
            # 6. Cleanup (뒷정리)
            # -----------------------------------------------------------------
            # 성공/실패 여부와 상관없이 로봇과 장비를 안전한 상태로 되돌려놓는다
            EVENT_BUS.data.sequence_job_finished.emit()
            
            try:
                # 사용했던 신호(DI43, DI44)는 반드시 끈다. 안 끄면 다음 실행 때 오작동한다
                robot.write_digital_signal(FanucSignal.DATA_READY_DI43, False)
                robot.write_digital_signal(FanucSignal.SYNC_START_TRIGGER_DI44, False)
                
                # Homing 수행 (항상 원점으로 복귀하여 안전 확보)
                servo.home_all_safely(timeout=30.0)
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] Homing 수행", "DEBUG")
                
            except Exception as e:
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 클린업 도중 오류 발생: {e}", "WARNING")

            # 이벤트 리스너 해제 (메모리 누수 방지)
            try:
                robot.remove_notification(handle_calc)
                robot.remove_notification(handle_motion)
                servo.remove_notification(handle_turntable)
            except: pass    # finally 블록 내부이므로 에러가 발생해도 전체 프로세스가 멈추면 안 되기 때문
    
    def _wait_event_with_safety(self, event: threading.Event, timeout: float) -> bool:
        """
        목적: 
            긴 시간(예: 60초) 동안 이벤트를 기다릴 때, 사용자의 '정지(Stop)' 요청에 즉각 반응하기 위함.
        
        원리:
            event.wait(timeout)을 한 번에 호출하면 그 시간 동안은 스레드가 완전히 멈춰서(Blocking)
            외부의 정지 신호(QThread.requestInterruption)를 감지할 수 없다.
            이를 방지하기 위해 0.1초씩 잘게 쪼개서 대기하며, 사이사이에 "중단 요청 왔나?" 하고 확인한다.
        """
        start = time.time()
        while time.time() - start < timeout:
            # 1. 사용자가 STOP 버튼을 눌렀는지 체크 (안전)
            if (t := QThread.currentThread()) and t.isInterruptionRequested():
                return False
            
            # 2. 0.1초만 대기 (Wait)
            if event.wait(0.1):
                return True # 이벤트가 발생했으면 즉시 성공 리턴
                
        return False # 시간 초과
        
    def _is_interrupted(self) -> bool:
        return bool((thread := QThread.currentThread()) and thread.isInterruptionRequested())


class LegacyIntegratedExecutor(BaseExecutor):
    """
    레거시 TXT 파일 형식
    """

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        data_keys = set(sample_data.keys())
        # TXT 레거시 키 (axis_x, Y...) 와 서보 키가 공존할 때
        has_legacy_robot = any(k in data_keys for k in ['axis_x', 'axis_y', 'axis_z', 'feed_rate'])
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        return has_legacy_robot and has_servo

    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 레거시 파일 모드로 실행 (데이터 {len(sequence_data)}건)", "INFO")

        return True, "레거시 파일 모드 실행 완료 -> TODO: 로직 만들어야 된다"



class TwinCATCommander(QObject):
    # =========================================================
    # 3. 게이트웨이 (The Commander)
    # =========================================================
    def __init__(self, connector: TwinCATConnector, fanuc: FanucAdapter, servo: ServoAdapter):
        super().__init__()                                  # QObject 초기화
        self._log_prefix = f"[{self.__class__.__name__}]"   # 로그 머릿말(발생 위치)
        self.connector = connector                          # 주입받은 TwinCAT 연결 저장
        
        # 하위 장치 컨트롤러 - 주입받은 것을 저장해서 사용
        self.robot = fanuc
        self.servo = servo

        # 등록된 실행기들 (우선순위 순서대로)
        # INTEGRATED(가장 구체적) -> ONLY(일반적) 순으로 배치
        self.executors: List[BaseExecutor] = [
            IntegratedExecutor(self.robot, self.servo),         # CSV 통합
            LegacyIntegratedExecutor(self.robot, self.servo),   # TXT 레거시 통합
            FanucOnlyExecutor(self.robot, self.servo),          # 로봇 단독
            ServoOnlyExecutor(self.robot, self.servo)           # 서보 단독
        ]

    def execute_sequence_with_executor(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        데이터 형식에 따라 적절한 Executor를 선택하여 실행하는 [게이트웨이]
            1. 데이터의 첫 줄을 샘플로 채취하여 적절한 실행기를 찾는다
            2. 찾은 Executor를 실행한다
        """
        
        if not sequence_data:
            return False, "데이터가 비어있습니다."

        sample_row = sequence_data[0]
        EVENT_BUS.log.message.emit(f"입력된 자료에 맞는 Excutor 선택을 위한 샘플 데이터(sequence_data[0]): {sample_row}", "DEBUG")

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
    # --- 비상 정지 명령 (로봇&서보)--- #
    # ================================= #
    def emergency_stop(self) -> tuple[bool, str]:
        """
        [비상 정지] 로봇과 서보를 즉시 정지시킴
        """
        results = []
        
        # 1. 로봇 비상 정지 (CycleStop)
        if self.robot:
            try:
                self.robot.set_emergency_stop()
                results.append("로봇정지: 성공")
            except Exception as e:
                results.append(f"로봇정지: 실패({e})")
        else:
            results.append("로봇정지: 연결없음")

        # 2. 서보 비상 정지 (Power Off)
        if self.servo:
            try:
                self.servo.turn_off_all_servos()
                results.append("서보정지: 성공 (전원 차단)")
            except Exception as e:
                results.append(f"서보정지: 실패({e})")
        else:
            results.append("서보정지: 연결없음")
            
        return True, ", ".join(results)




    # ================================= #
    # --- 로봇에게 내리는 명령들 --- #
    # ================================= #
    def apply_user_feed_rate_when_moving_robot(self, feed_rate: float) -> str | None:
        """RobotControllerWidget 에서 사용자가 입력한 Feed Rate 값을 FANUC에 적용"""

        # 로봇이 움직이고 있는지 확인
        is_robot_moving = self.robot.read_busy_signal()

        if is_robot_moving:
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
            try:
                robot_busy = self.robot.read_busy_signal()
            except Exception:
                # 로봇 연결이 없거나 변수가 없을 때 에러 무시 (False 반환)
                robot_busy = False

        # 서보모터 상태 확인 (모든 3축 확인)
        servo_busy = False
        if self.servo:
            try:
                servo_busy = any(self.servo.is_servo_moving_physically(axis) for axis in ServoAxis)
            except Exception as e:
                # 반복 호출되므로 로그 레벨을 DEBUG로 낮춤
                EVENT_BUS.log.message.emit(f"서보모터 상태 확인 중 오류: {e}", "DEBUG")
                servo_busy = False

        # 둘 중 하나라도 바쁘면 시스템은 바쁜 것
        return robot_busy or servo_busy

    def start_sequence_plc_signals(self) -> tuple[bool, str]:
        """로봇에게 시작 신호(RSR, Loop 등) 전송"""
        if self.robot:
            try:
                self.robot.set_initial_signals()
                return True, "시작 신호 전송 완료"
            except Exception as e:
                # 1808: Symbol not found (Servo Only 모드)
                if "symbol not found" in str(e).lower() or "1808" in str(e):
                    EVENT_BUS.log.message.emit(f"로봇 시작 신호 전송 실패 (변수 없음): {e}", "WARNING")
                    return True, "로봇 연결 없음 (무시됨)"

                return False, f"시작 신호 전송 실패: {e}"
        return False, "로봇이 연결되지 않았습니다."

    def end_sequence_plc_signals(self) -> tuple[bool, str]:
        """로봇에게 종료/정지 신호 전송"""
        if self.robot:
            try:
                self.robot.set_finish_signals()
                return True, "종료 신호 전송 완료"
            except Exception as e:
                # 1808: Symbol not found (Servo Only 모드)
                # 로봇이 없어도 서보 정지 등 후속 작업을 위해 True 반환
                if "symbol not found" in str(e).lower() or "1808" in str(e):
                    EVENT_BUS.log.message.emit(f"로봇 정지 신호 전송 실패 (변수 없음): {e}", "WARNING")
                    return True, "로봇 연결 없음 (무시됨)"

                return False, f"종료 신호 전송 실패: {e}"
        return False, "로봇이 연결되지 않았습니다."


    # ================================= #
    # --- 서보(Panasonic) 제어 명령 --- #
    # ================================= #
    def is_servo_on(self, axis: ServoAxis) -> bool:
        """서보 전원이 켜져 있는지 확인 (브릿지)"""
        if self.servo:
            return self.servo.is_servo_on(axis.value)
        return False

    def set_servo_state(self, axis: ServoAxis, enable: bool):
        """서보 전원 상태 설정 (브릿지)"""
        if self.servo:
            self.servo.set_servo_state(axis.value, enable)

    def shutdown_servos_safely(self) -> tuple[bool, str]:
        """
        [브릿지] 서보를 안전하게 정지시키고 전원을 차단하도록 시킴
        Worker -> Commander -> Adapter 순으로 명령 전달
        """
        if self.servo:
            # Adapter의 '명확한 이름'의 메서드를 호출
            success = self.servo.shutdown_all_with_power_off()
            
            msg = "모든 서보가 안전하게 정지 및 해제되었습니다." if success else "서보 종료 처리 중 오류 발생"
            return success, msg
        
        return False, "서보 어댑터가 연결되지 않았습니다."


    def home_servos_safely(self) -> tuple[bool, str]:
        """
        [브릿지] 서보의 안전 원점 복귀 절차를 실행하도록 시킴
        """
        if not self.servo:
            return False, "서보 어댑터가 연결되지 않았습니다."

        # 원점 복귀 시작 전 바쁨 상태 방송
        EVENT_BUS.data.servo_physical_moving_status_changed({'is_servo_moving': True})

        try:
            # Adapter에게 원점 복귀 절차 위임
            success = self.servo.home_all_safely()
            msg = "서보 원점 복귀 명령 전송 완료" if success else "원점 복귀 중 오류 발생"
            return success, msg
        except Exception as e:
            return False, f"서보 원점 복귀 중 예외 발생: {e}"
        finally:
            # 성공/실패 여부에 상관없이 마지막에는 바쁨 상태 해제
            EVENT_BUS.data.servo_physical_moving_status_changed({'is_servo_moving': False})


    def reset_servos_safely(self) -> tuple[bool, str]:
        """서보 축의 에러 상태 해제"""
        if not self.servo: 
            return False, "서보 어댑터가 연결되지 않았습니다."

        try:
            results = []
            # 모든 축에 대해 에러 리셋 시도
            for axis in ServoAxis:
                # clear_error_pulse는 내부적으로 에러가 있을 때만 리셋 동작을 수행함
                is_cleared = self.servo.clear_error_pulse(axis.value)
                results.append(is_cleared)
            
            if all(results):
                return True, "모든 서보 축의 에러가 리셋되었습니다."
            else:
                return False, "일부 축의 에러 리셋에 실패했습니다."
        except Exception as e:
            return False, f"서보 리셋 중 오류 발생: {e}"