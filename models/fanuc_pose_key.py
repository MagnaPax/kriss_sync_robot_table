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
    """
    FANUC 로봇 제어 신호 키 (Key) 정의
    
    구조체 방식에서는 모델(FANUCPose)의 to_struct() 메서드에서 '이름(Key)'으로 값을 찾는다
    (Service -> Model 전달용)
    """
    # =========================================================
    # [입력] Robot <- PLC (보내는 신호: Trigger/DataReady)
    # 키 이름은 FANUCPose.to_struct() 메서드 내부 로직과 일치해야 함
    # =========================================================
    IMSP =          "IMSP"          # Immediate Stop    즉시 멈춰라(OFF)    즉시 멈춤 신호 해제는 On
    HOLD =          "Hold"          # Hold              일시정지
    SFSP =          "SFSP"          # Safety Speed      안전 속도
    ENABLE =        "Enable"        # Enable            동작 실행 가능 여부 확인
    """
    ⬆️ 기본적으로 이 위의 신호가 켜져야 로봇이 동작한다 ⬆️
    """
    CYCLE_STOP =    "CycleStop"     #                   테스트 중
    FAULT_RESET =   "FaultReset"    # Fault Reset       (Fault 원인 제거 후) -> 이 신호를 Falling Edge가 되면 정상 상태가 된다. (원인 제거를 안 하면 계속 FAULT 신호가 유지됨)
    START =         "Start"         # Start             (아마도) 일시 정지 후 재시작 할 때
    HOME =          "Home"          # Home              (아마도) Home 위치로 이동할 때
    
    RSR1 =          "RSR1"          # Robot Service Request 1   원격으로 로봇의 TP 프로그램 실행하고 싶을때 사용 (최종적으로 어떤 신호를 사용할지는 미정)
    RSR2 =          "RSR2"          # Robot Service Request 2   원격으로 로봇의 TP 프로그램 실행하고 싶을때 사용
    RSR3 =          "RSR3"          # Robot Service Request 3   원격으로 로봇의 TP 프로그램 실행하고 싶을때 사용
    RSR4 =          "RSR4"          # Robot Service Request 4   원격으로 로봇의 TP 프로그램 실행하고 싶을때 사용
    RSR5 =          "RSR5"          # Robot Service Request 5   원격으로 로봇의 TP 프로그램 실행하고 싶을때 사용
    RSR6 =          "RSR6"          # Robot Service Request 6   원격으로 로봇의 TP 프로그램 실행하고 싶을때 사용
    RSR7 =          "RSR7"          # Robot Service Request 7   원격으로 로봇의 TP 프로그램 실행하고 싶을때 사용
    RSR8 =          "RSR8"          # Robot Service Request 8   원격으로 로봇의 TP 프로그램 실행하고 싶을때 사용
    
    # DI43: 이동 시작 트리거 (Start Trigger)
    #       매 스텝마다 데이터 전송 후, Low -> High (Rising Edge)로 펄스를 주어
    #       로봇에게 시퀀스를 보낸다는 신호
    TRIGGER_DI43 = "DI43"          
    
    # DI44: 루프 상태 신호 (Loop Signal)
    #       시퀀스가 시작되면 High로 켜지고, 전체 작업이 끝날 때까지 유지된다.
    #       로봇은 이 신호가 켜져 있어야 Handshake 루프를 계속 돈다.
    LOOP_DI44 = "DI44"
    

    # =========================================================
    # [출력] Robot -> PLC (읽는 신호: Handshake/Status)
    # =========================================================

    # 로봇이 시퀀스(한 줄)을 받았다는 확인 신호
    #   이 신호가 TRUE 되면 다음 데이터를 전송하고 DI43을 트리거한다.
    ROBOT_MOTION_DONE = "MAIN.Robot1._UO1.DO46"

    BUSY =      "MAIN.Robot1._UO1.UO10_Busy"        # 바쁨 신호
    PAUSED =    "MAIN.Robot1._UO1.UO04_PrgPaused"   # 일시정지
    FAULT =     "MAIN.Robot1._UO1.UO06_Fault"       # 에러


    @property
    def path(self) -> str:
        """PLC 주소 반환"""
        return self.value
