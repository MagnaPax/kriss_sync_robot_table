# models/servo_pose_key.py
from enum import Enum

class ServoPoseKey(str, Enum):
    """
    턴테이블 제어 데이터(Target)의 키 정의 및 PLC 주소 매핑
    
    역할:
        - 딕셔너리 키 관리 ('angle', 'velocity')
        - PLC Write 주소 관리 ('MAIN.position', 'MAIN.velocity')
    """
    ANGLE = "MAIN.position"      # 목표 각도
    VELOCITY = "MAIN.velocity"   # 회전 속도

    @property
    def model_key(self) -> str:
        """
        데이터 모델(ServoPose)이나 딕셔너리에서 사용하는 키 반환
        """
        if self == ServoPoseKey.ANGLE:
            return "angle"
        elif self == ServoPoseKey.VELOCITY:
            return "velocity"
        return ""

    @property
    def unit(self) -> str:
        """UI 표시용 단위"""
        if self == ServoPoseKey.ANGLE:
            return "deg"
        return "deg/s"

    @property
    def plc_address(self) -> str:
        """PLC 변수 주소 (값 그 자체)"""
        return self.value


# =============================================================================
# 제어 신호 정의 (Control Signals)
# =============================================================================
class TurntableSignal(str, Enum):
    """
    턴테이블 제어/상태 확인을 위한 PLC 주소 모음
    """
    # [입력] PC -> PLC (Write)
    SERVO_ON     = 'MAIN.bServoOn'      # 서보 모터 전원 ON/OFF
    MOVE_START   = 'MAIN.bMoveAbsOn'    # 이동 시작 트리거 (Rising Edge)
    READ_POS_ON  = 'MAIN.bReadPosOn'    # (옵션) 위치 읽기 활성화

    # [출력] PLC -> PC (Read)
    BUSY         = 'MAIN.bMoveAbsBusy'  # 이동 중 (True=Busy)
    CURRENT_POS  = 'MAIN.CurrentPos'    # 현재 위치 피드백 (LREAL)

    @property
    def path(self) -> str:
        """PLC 주소 반환"""
        return self.value
