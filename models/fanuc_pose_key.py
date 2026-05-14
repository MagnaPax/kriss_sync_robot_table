# models/fanuc_pose_key.py
"""
목적:
    오타 방지 / 축 이름 관리

역할:
    상수(Enum)

동작:
    상태 없음(stateless)
"""
from enum import Enum

class FANUCPoseKey(str, Enum):
    """
    FANUC 로봇의 6개 움직임(pose) 이름 정의 및 PLC 주소 생성기

    [개념 설명]
    로봇 팔은 6개의 자유도(6-DoF)를 가진다
    1. 위치 (Position): 공구 끝이 공간상 어디에 '있는'가? -> X, Y, Z (mm)
    2. 자세 (Orientation): 공구 끝이 어디를 '바라보는'가? -> W, P, R (deg)

    [이 클래스의 역할]
    1. 오타 방지: "x" 대신 FANUCPoseKey.X 사용
    2. 단위 관리: 위치(mm)와 회전(deg) 구분
    3. PLC 주소 자동 생성: 'X'만 주면 복잡한 비트 주소를 알아서 만들어줌

    [비유]
    - FANUCPoseKey (Enum): 메뉴판의 '메뉴 이름' (예: "불고기버거")
    - FANUCPose (DataClass): 실제 주문서 (예: "불고기버거 1개, 콜라 2개")
    """

    # --- 위치 (Linear: 직선 이동) ---
    X = "X" # 로봇 앞/뒤 거리
    Y = "Y" # 로봇 좌/우 거리
    Z = "Z" # 로봇 위/아래 높이

    # --- 자세 (Rotation: 회전) ---
    W = "W" # Yaw (X축을 중심으로 회전)
    P = "P" # Pitch (Y축을 중심으로 회전)
    R = "R" # Roll (Z축을 중심으로 회전)

    @property
    def model_key(self) -> str:
        """
        PLC용 대문자 이름을 내부용 소문자 이름으로 바꿔주는 번역기 역할

        설명:
            Python 코드는 관습적으로 소문자 변수명을 사용한다
            하지만 PLC의 메모리 주소, 태그 이름 등은 보통 대문자로 되어 있다
            이 함수는 중간에서 대문자를 소문자로 바꿔주는 기능

        예시:
            FANUCPoseKey.X.model_key -> "x"
        """
        return self.value.lower()

    @property
    def unit(self) -> str:
        """
        해당 축의 물리적 단위 반환 (UI 표시용)

        설명:
            - X, Y, Z는 거리이므로 밀리미터(mm)를 사용
            - W, P, R은 회전 각도이므로 도(degree)를 사용
        """

        if self in [FANUCPoseKey.X, FANUCPoseKey.Y, FANUCPoseKey.Z]:
            return "mm"
        return "deg"



# =============================================================================
# 제어 신호 정의
# =============================================================================
class FanucSignal(str, Enum):
    """FANUC 로봇 제어 신호 키 (Key) 정의"""

    # ==================================
    #       [출력] PLC ⬅️ Robot
    # ==================================

    # (받을 준비가 됐으니) 새로운 데이터를 달라
    ROBOT_SIGNAL_VAR = "MAIN.Robot1._UO1.DO46"

    # 오류 발생시 ON
    FAULT_STATUS = "MAIN.Robot1._UO1.UO06_Fault"

    # 로봇 BUSY 신호 -> 로봇이 움직이고 있을때 ON
    ROBOT_BUSY_STATUS = "MAIN.Robot1._UO1.UO10_Busy"




    # ==================================
    #       [입력] PLC ➡️ Robot
    # ==================================

    # 데이터 버퍼 (Sequence 50개 * 3 = 150개)
    # MAIN.send_buffer{Group}_{SubIndex} 패턴 사용 (FanucAdapter에서 동적 생성)

    # 즉시 멈춤 - 평상시 ON 상태, OFF하면 즉시 정지
    IMSP = "MAIN.Robot1._UI1.UI01_IMSP"

    # 일시정지 - 평상시 ON 상태, OFF하면 즉시 정지
    HOLD = "MAIN.Robot1._UI1.UI02_Hold"

    # 안전속도 - 사람이 접근시 속도 늦추기(평상시 ON)
    SFSP = "MAIN.Robot1._UI1.UI03_SFSP"

    # 신호가 켜져었어야 동작 가능(평상시 ON)
    ENABLE = "MAIN.Robot1._UI1.UI08_Enable"

    """⬆️ 위 신호 4개가 ON이 되어야 로봇 동작 가능 ⬆️"""

    # 사이클 정지 - 평상시 OFF 상태, ON하면 사이클 정지
    CYCLE_STOP = "MAIN.Robot1._UI1.UI04_CycleStop"

    # 오류 원인 제거 후 실행(Falling Edge로 동작)
    FAULT_RESET = "MAIN.Robot1._UI1.UI05_FaultReset"

    # 재시작
    RESUME = "MAIN.Robot1._UI1.UI06_Start"

    # Home 위치로 이동
    HOME = "MAIN.Robot1._UI1.UI07_Home"

    # TP 프로그램 시작 - ON(Rising Edge)이 되면 FANUC 로봇이 동작하는 FANUC TP Program을 실행
    RSR1 = "MAIN.Robot1._UI1.UI09_RSR1"     # 로봇-서보 동시 동작(시퀀스)용
    RSR2 = "MAIN.Robot1._UI1.UI10_RSR2"     # 로봇 단독 동작용
    RSR3 = "MAIN.Robot1._UI1.UI11_RSR3"
    RSR4 = "MAIN.Robot1._UI1.UI12_RSR4"
    RSR5 = "MAIN.Robot1._UI1.UI13_RSR5"
    RSR6 = "MAIN.Robot1._UI1.UI14_RSR6"
    RSR7 = "MAIN.Robot1._UI1.UI15_RSR7"
    RSR8 = "MAIN.Robot1._UI1.UI16_RSR8"


    # 시퀀스 전달 실행 신호
    EXECUTE = "MAIN.bExecute"

    # 데이터 서비스 코드
    SERVICE_CODE = "MAIN.nServiceCode"

    # 데이터 클래스
    CLASS = "MAIN.nClass"

    # 데이터 인스턴스
    INSTANCE = "MAIN.nInstance"

    # 지정된 Robot의 NUMREG 주소 (HEX)
    ATTRIBUTE = "MAIN.nAttribute"

    # 시퀀스 개수
    NUMBER_OF_DATA = "MAIN.nNumberofData"

    # 버퍼 번호 (예: 11 -> send_buffer1_1)
    BUFFER_ID = "MAIN.nBufferID"



    # ==================
    #
    # ==================

    # 데이터 설정
    CHUNK_SIZE = 100    # 경로 단순화 청크 크기
    BUFFER_SIZE = 150   # PLC 버퍼 크기
    
    # Explicit Message관련(nBufferID, nAttribute)
    BUFFER_MAPPING = [
        (11, 1), (12, (BUFFER_SIZE + 1)), (13, (2 * BUFFER_SIZE + 1)),
        (21, (3 * BUFFER_SIZE + 1)), (22, (4 * BUFFER_SIZE + 1)), (23, (5 * BUFFER_SIZE + 1))
    ]



    # ==================
    #
    # ==================

    # [정지 및 재시작 신호]
    FR_ROBOT_HOLD_VAR   = 'MAIN.Robot1._UI1.UI02_Hold'  # 기본 True,  일시정지 -> False
    FR_ROBOT_RESUME_VAR = 'MAIN.Robot1._UI1.UI06_Start' # 기본 False, 다시 시작 -> True

    # [Homing 신호]
    FR_ROBOT_HOME_VAR   = 'MAIN.Robot1._UI1.UI07_Home'  # 기본 False, Homing -> True

    # [로봇 통신 변수]
    FR_ROBOT_SIGNAL_VAR = 'MAIN.Robot1._UO1.DO46'   # 로봇으로부터 시퀀스 갱신 신호

    # [모니터링 변수] 
    # 로봇이 보내는 비트 신호가 양수인지 음수인지
    FR_SIGN_BIT_MAP = {
        "X" : "MAIN.Robot1._UO1.X_Check",
        "Y" : "MAIN.Robot1._UO1.Y_Check",
        "Z" : "MAIN.Robot1._UO1.Z_Check",
        "W" : "MAIN.Robot1._UO1.W_Check",
        "P" : "MAIN.Robot1._UO1.P_Check",
        "R" : "MAIN.Robot1._UO1.R_Check",
    }

    # [데이터 저장용 버퍼]
    FR_BUFFER_FOR_SEQUENCE_MOVE = "MAIN.send_single_buffer" # 목적지 데이터 저장용 버퍼 - 서보모터와 함께 움직이는 시퀀스 동작용
    FR_BUFFER_FOR_MANUAL_MOVE   = "MAIN.goto_buffer"        # 목적지 데이터 저장용 버퍼 - 로봇 단독 동작용


    # ==================
    #
    # ==================

    FR_BUFFER_SIZE      = 150




    @property
    def path(self) -> str:
        """PLC 주소 반환"""
        return self.value