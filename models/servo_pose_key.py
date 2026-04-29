# models/servo_pose_key.py

from enum import Enum, IntEnum
import ctypes


class ServoAxis(IntEnum):
    """
    서보 모터 축 번호 매핑 (1-based index)
    1, 2, 3 숫자 대신 물리적 역할이 담긴 직관적인 이름을 사용한다.
    """
    TOOL_REVOLUTION = 1     # 툴 공전 (Revolution)
    TOOL_ROTATION = 2       # 툴 자전 (Rotation)
    TURNTABLE = 3           # 턴테이블 (Turntable)


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

    # [설정] - 나중에 1(공전),2(자전),3(턴테이블)을 끼워넣을 수 있도록
    SERVO_ON     = 'MAIN.bServoOn{}'    # 서보 전원 (BOOL)
    READ_POS_ON  = 'MAIN.bReadPos{}'    # 위치 표시 (BOOL)  TwinCAT PLC 에서 자동으로 켜짐
    READ_VEL_ON  = 'MAIN.bReadVel{}'    # 속도 표시 (BOOL)  TwinCAT PLC 에서 자동으로 켜짐

    # [명령]
    STOP         = 'MAIN.bStop{}'       # 정지 (BOOL)
    START_ALL    = 'MAIN.bStart'        # '모든' 서보 동작 신호
    
    # [이동 - 위치 제어 (턴테이블용)]
    MOVE_ABS     = 'MAIN.bMoveAbs{}'    # 절대 위치 이동 시작 (BOOL)    사용 안 함
    TARGET_POS   = 'MAIN.pos{}'         # 목표 위치 입력 (LREAL)        사용 안 함
    TT_PATH_DATA = 'MAIN.aPathData'     # 턴테이블의 ((목표 속도 & 목표 좌표) = 한 쌍) 저장. 1000쌍 저장 가능. 인덱스 1번부터 시작


    # [이동 - 속도 제어 (툴 모터용)]
    MOVE_VEL     = 'MAIN.bMoveVel{}'    # 속도 제어 이동 시작 (BOOL)    
    
    # [원점 복구]
    HOME         = 'MAIN.bHome{}'       # 원점 복귀 시작 (Rising Edge) (BOOL)
    
    # [공통 입력]
    TARGET_VEL   = 'MAIN.lVel{}'        # 목표 속도 입력 (LREAL)        이 값에 입력된 속도로 돌아라 (위치/속도 모드 공용)
    
    # [상태 확인]
    DONE         = 'MAIN.bDone{}'       # 이동 완료 (Rising Edge) (BOOL)

    # [피드백 (Read)]
    BUSY         = 'MAIN.bBusy{}'       # 이동 중 여부 (BOOL)           켜지면 다른 명령 받아도 write 안 함
    ACT_POS      = 'MAIN.lAct_Pos{}'    # 현재 위치 (LREAL)
    ACT_VEL      = 'MAIN.lAct_Vel{}'    # 현재 속도 (LREAL)

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



# =============================================================================
# 
# =============================================================================

    # [정지 및 재시작 신호]
    SM_STOP_VAR         = 'GVL.bStop'                   # Turn Table Stop
    SM_STOP_REV_VAR     = 'GVL.bStop_rev'               # 자전 Stop
    SM_STOP_ROT_VAR     = 'GVL.bStop_rot'               # 공전 Stop
    SM_RESUME_VAR       = 'GVL.bRestart'                # Stop 시 Resume 신호

    # [Homing]
    SM_SINGLE_HOME_VAR  = 'GVL.bHome'                   # Turn Table Homing

    # [단일 모터 신호 정의]
    SM_SINGLE_POS_VAR   = 'MAIN.nPos'                   # 턴테이블 단독 동작 위치
    SM_SINGLE_VEL_VAR   = 'MAIN.nVel'                   # 턴테이블 단독 동작 속도
    SM_SINGLE_START_VAR = 'GVL.bStart2'                 # 턴테이블 단독 동작 신호 - 이동할 데이터들을 미리 보낸 뒤 이 신호를 올리면 (서보 단독) 동작 시작

    # [서보 모터 통신 변수] 서보 모터로부터 시퀀스 갱신 신호들
    SM_VAR_REQ_LOWER    = 'GVL.bReqUpdateLower'     
    SM_VAR_REQ_UPPER    = 'GVL.bReqUpdateUpper'
    SM_VAR_UPD_DONE     = 'GVL.bUpdateDone'
    SM_VAR_ALL_FIN      = 'GVL.bAllDataFinished'
    SM_VAR_PATH_ARR     = 'GVL.aPathData'

    # 서보 모터의 위치(Turn Talbe), 속도(공전,자전)
    SM_MONITOR_POS      = 'MAIN.fServoCurrPos'
    SM_MONITOR_VEL_REV  = 'MAIN.fServoCurrVel_rev'
    SM_MONITOR_VEL_ROT  = 'MAIN.fServoCurrVel_rot'



# =============================================================================
# 턴테이블 데이터 구조 정의 (Data Structure Definitions)
# =============================================================================

# 시퀀스 동작을 위한 서보 모터 제어 구조체
class ST_PathData(ctypes.Structure):
    _pack = 1
    _fields_ = [
        ('fPosition', ctypes.c_double),
        ('fVelocity', ctypes.c_double),
        ('fVelocity2', ctypes.c_double),
        ('fVelocity3', ctypes.c_double)
    ]


Array500 = ST_PathData * 500

