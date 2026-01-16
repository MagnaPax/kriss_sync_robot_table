# communication/twincat_commander.py
"""
TwinCAT Commander (Controller/Gateway Layer)

이 모듈은 상위 UI/Logic 계층과 하위 하드웨어 제어(TwinCAT/Robot/Servo) 사이의
중앙 통제실(Gateway) 역할을 수행한다.

[핵심 기능]
1. 전략 패턴(Strategy Pattern) 운용:
    - 입력된 데이터의 형태(CSV, 로봇 단독, 서보 단독 등)를 분석한다.
    - 적절한 실행 전략(Executor)을 자동으로 선택하여 작업을 위임한다.
    - 예: `IntegratedExecutor`, `FanucOnlyExecutor` 등

2. 통합 기기 제어:
    - FANUC 로봇과 Panasonic 서보 모터의 연결 상태를 관리한다.
    - 비상 정지(E-Stop), 원점 복귀(Homing), 에러 리셋 등 공통 명령을 처리한다.
"""
from typing import List, Any, Dict
from PyQt6.QtCore import QObject

from core.event_bus import EVENT_BUS
from models.servo_pose_key import ServoAxis
from communication.fanuc_adapter import FanucAdapter
from communication.servo_adapter import ServoAdapter
from communication.twincat_connector import TwinCATConnector
from communication.execution_strategies import (
    BaseExecutor,
    FanucOnlyExecutor,
    ServoOnlyExecutor,
    IntegratedExecutor,
    LegacyIntegratedExecutor
)



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
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 입력된 자료에 맞는 Excutor 선택을 위한 샘플 데이터(sequence_data[0]): {sample_row}", "DEBUG")

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
    # --- 일반 정지 (로봇&서보) --- #
    # ================================= #
    def stop_robot_servo_normally(self) -> tuple[bool, str]:
        """
        [일반 정지] 로봇과 서보를 정상적으로 정지시킴 (작업 중단 시 사용)
            - 로봇: CYCLE_STOP 등 부드러운 정지 신호
            - 서보: 감속 정지
        """
        results = []
        
        # 1. 로봇 정지
        if self.robot:
            try:
                self.robot.stop_fanuc_normally()
                results.append(f"{self._log_prefix} 로봇 정지 신호 전송")
            except Exception as e:
                results.append(f"{self._log_prefix} 로봇 정지 실패: {e}")
        
        # 2. 서보 정지 ( 즉시 정지 요청 활용)
        if self.servo:
            try:
                self.servo.request_immediate_stop()
                results.append(f"{self._log_prefix} 서보 정지 요청 전송")
            except Exception as e:
                results.append(f"{self._log_prefix} 서보 정지 실패: {e}")

        # 서보 바쁨 상태 해제
        EVENT_BUS.control.servo_physical_moving_status_changed.emit({'is_servo_moving': False})
        
        return True, ", ".join(results)


    # ================================= #
    # --- 비상 정지 명령 (로봇&서보)--- #
    # ================================= #
    def emergency_stop_servo_and_robot(self) -> tuple[bool, str]:
        """
        [비상 정지] 로봇과 서보를 즉시 정지시킴
        """
        results = []
        
        # 1. 로봇 비상 정지 (CycleStop)
        if self.robot:
            try:
                self.robot.set_emergency_stop()
                results.append(f"{self._log_prefix} 로봇정지: 성공")
            except Exception as e:
                results.append(f"{self._log_prefix} 로봇정지: 실패({e})")
        else:
            results.append("로봇정지: 연결없음")

        # 2. 서보 비상 정지 (Power Off)
        if self.servo:
            try:
                self.servo.turn_off_all_servos()
                results.append(f"{self._log_prefix} 서보정지: 성공 (전원 차단)")
            except Exception as e:
                results.append(f"{self._log_prefix} 서보정지: 실패({e})")
        else:
            results.append(f"{self._log_prefix} 서보정지: 연결없음")
            
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

    def start_robot_plc_signals(self) -> tuple[bool, str]:
        """로봇에게 시작 신호(RSR, Loop 등) 전송"""
        if self.robot:
            try:
                self.robot.set_initial_signals()
                return True, "시작 신호 전송 완료"
            except Exception as e:
                # 1808: Symbol not found (Servo Only 모드)
                if "symbol not found" in str(e).lower() or "1808" in str(e):
                    EVENT_BUS.log.message.emit(f"{self._log_prefix} 로봇 시작 신호 전송 실패 (변수 없음): {e}", "WARNING")
                    return True, "로봇 연결 없음 (무시됨)"

                return False, f"시작 신호 전송 실패: {e}"
        return False, "로봇이 연결되지 않았습니다."

    def stop_robot_plc_signals(self) -> tuple[bool, str]:
        """로봇에게 종료/정지 신호 전송"""
        if self.robot:
            try:
                self.robot.set_finish_signals()
                return True, "종료 신호 전송 완료"
            except Exception as e:
                # 1808: Symbol not found (Servo Only 모드)
                # 로봇이 없어도 서보 정지 등 후속 작업을 위해 True 반환
                if "symbol not found" in str(e).lower() or "1808" in str(e):
                    EVENT_BUS.log.message.emit(f"{self._log_prefix} 로봇 정지 신호 전송 실패 (변수 없음): {e}", "WARNING")
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
            
            msg = f"{self._log_prefix} 모든 서보가 안전하게 정지 및 해제되었습니다." if success else f"{self._log_prefix} 서보 종료 처리 중 오류 발생"
            return success, msg
        
        return False, f"{self._log_prefix} 서보 어댑터가 연결되지 않았습니다."


    def home_servos_safely(self) -> tuple[bool, str]:
        """
        [브릿지] 서보의 안전 원점 복귀 절차를 실행하도록 시킴
        """
        if not self.servo:
            return False, f"{self._log_prefix} 서보 어댑터가 연결되지 않았습니다."

        # 원점 복귀 시작 전 바쁨 상태 방송
        EVENT_BUS.control.servo_physical_moving_status_changed({'is_servo_moving': True})

        try:
            # Adapter에게 원점 복귀 절차 위임
            success = self.servo.home_all_safely()
            msg = f"{self._log_prefix} 서보 원점 복귀 명령 전송 완료" if success else f"{self._log_prefix} 원점 복귀 중 오류 발생"
            return success, msg
        except Exception as e:
            return False, f"{self._log_prefix} 서보 원점 복귀 중 예외 발생: {e}"
        finally:
            # 성공/실패 여부에 상관없이 마지막에는 바쁨 상태 해제
            EVENT_BUS.control.servo_physical_moving_status_changed({'is_servo_moving': False})


    def reset_servos_safely(self) -> tuple[bool, str]:
        """서보 축의 에러 상태 해제"""
        if not self.servo: 
            return False, f"{self._log_prefix} 서보 어댑터가 연결되지 않았습니다."

        try:
            results = []
            # 모든 축에 대해 에러 리셋 시도
            for axis in ServoAxis:
                # clear_error_pulse는 내부적으로 에러가 있을 때만 리셋 동작을 수행함
                is_cleared = self.servo.clear_error_pulse(axis.value)
                results.append(is_cleared)
            
            if all(results):
                return True, f"{self._log_prefix} 모든 서보 축의 에러가 리셋되었습니다."
            else:
                return False, f"{self._log_prefix} 일부 축의 에러 리셋에 실패했습니다."
        except Exception as e:
            return False, f"{self._log_prefix} 서보 리셋 중 오류 발생: {e}"



    # ================================= #
    # --- 로봇&서보 공통 명령 --- #
    # ================================= #
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
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보모터 상태 확인 중 오류: {e}", "DEBUG")
                servo_busy = False

        # 둘 중 하나라도 바쁘면 시스템은 바쁜 것
        return robot_busy or servo_busy

