# models/servo_pose_key.py
from enum import Enum, IntEnum



class ServoAxis(IntEnum):
    """
    서보 모터 축 번호 매핑 (1-based index)
    1, 2, 3 숫자 대신 물리적 역할이 담긴 직관적인 이름을 사용한다.
    """
    SPINDLE_REVOLUTION_AXIS_1 = 1  # 툴 공전 (Revolution)
    SPINDLE_ROTATION_AXIS_2   = 2  # 툴 자전 (Rotation)
    TURNTABLE_AXIS_3         = 3  # 턴테이블 (Turntable)


class ServoPoseKey(str, Enum):
    """서보모터 데이터 키 정의 (UI 표시 및 내부 로직용)"""

    ANGLE = "angle"         # 목표 각도
    VELOCITY = "velocity"   # 회전 속도

    @property
    def unit(self) -> str:
        """UI 표시용 단위"""
        if self == ServoPoseKey.ANGLE:
            return "deg"
        return "deg/s"


# =============================================================================
# 제어 신호 정의 (Control Signals) - 동적 주소 생성
# =============================================================================
class ServoSignal(str, Enum):
    """
    Panasonic 서보모터 제어/상태 확인을 위한 PLC 주소 템플릿

    특징:
        - 문자열 뒤에 축 번호가 붙는 구조 (예: MAIN.bServoOn1, MAIN.bServoOn2)
        - .path(index) 메서드를 통해 실제 주소를 생성
    """

    # [설정] - 나중에 1,2,3을 끼워넣을 수 있게
    SERVO_ON     = 'MAIN.bServoOn{}'    # 서보 전원 (BOOL)
    READ_POS_ON  = 'MAIN.bReadPos{}'    # 위치 읽기 활성화 (BOOL)
    READ_VEL_ON  = 'MAIN.bReadVel{}'    # 속도 읽기 활성화 (BOOL)

    # [명령]
    STOP         = 'MAIN.bStop{}'       # 정지 (BOOL)
    
    # [이동 - 위치 제어 (턴테이블용)]
    MOVE_ABS     = 'MAIN.bMoveAbs{}'    # 절대 위치 이동 시작 (BOOL)
    TARGET_POS   = 'MAIN.pos{}'         # 목표 위치 입력 (LREAL)

    # [이동 - 속도 제어 (툴 모터용)]
    MOVE_VEL     = 'MAIN.bMoveVel{}'    # 속도 제어 이동 시작 (BOOL)
    
    # [원점 복구]
    HOME         = 'MAIN.bHome{}'       # 원점 복귀 시작 (Rising Edge) (BOOL)
    
    # [공통 입력]
    TARGET_VEL   = 'MAIN.vel{}'         # 목표 속도 입력 (LREAL) - 위치/속도 모드 공용

    # [피드백 (Read)]
    BUSY         = 'MAIN.Busy{}'        # 이동 중 여부 (BOOL) - 명령 받아도 write ❌
    ACT_POS      = 'MAIN.Act_pos{}'     # 현재 위치 (LREAL)
    ACT_VEL      = 'MAIN.Act_vel{}'     # 현재 속도 (LREAL)

    # [에러]
    ERROR_ID     = 'MAIN.nErrorID{}'    # 에러 코드 (UDINT/UINT)
    ERROR_RESET  = 'MAIN.bReset{}'      # 에러 리셋 신호 (BOOL)
    ERROR_STATE  = 'MAIN.bError{}'      # 에러 발생 상태 (BOOL)

    def get_plc_path(self, axis_index: int) -> str:
        """
        축 번호를 받아 실제 PLC 주소(Tag Name)를 반환한다.
        
        Args:
            axis_index (int): 1, 2, 3 등 물리적 축 번호
            
        Returns:
            str: 완성된 PLC 심볼 경로 (예: 'MAIN.bServoOn1')
        """
        return self.value.format(axis_index)
