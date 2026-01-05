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

    # =========================================================
    # [삭제됨] 비트 단위 주소 생성 로직
    # 이유: 새로운 FanucUI1Struct 에서는 구조체를 통째로 쓰기 때문에
    #       개별 비트 주소를 생성할 필요가 없음 (모델 레벨에서 비트 패킹 수행)
    # ---------------------------------------------------------
    # def tag_check(self) -> str: ...
    # def tag_low_bit(self, bit_index: int) -> str: ...
    # def tag_high_bit(self, bit_index: int) -> str: ...
    # =========================================================
    pass


# =============================================================================
# 제어 신호 정의
# =============================================================================
class FanucSignal(str, Enum):
    """
    FANUC 로봇 제어 신호 키 (Key) 정의
    
    [변경 사항]
    이전에는 PLC 주소(예: "MAIN.Robot1._UI1.UI10_RSR2")를 직접 가졌으나,
    새로운 구조체 방식에서는 모델의 to_struct() 메서드에서 '이름(Key)'으로 값을 찾으므로
    단순한 문자열 키로 변경함. (Service -> Model 전달용)
    """
    # [입력] Robot <- PLC (보내는 신호)
    # 키 이름은 FANUCPose.to_struct() 메서드 내부 로직과 일치해야 함
    IMSP =          "IMSP"          # Immediate Stop
    HOLD =          "Hold"          # Hold
    SFSP =          "SFSP"          # Safety Speed
    CYCLE_STOP =    "CycleStop"     # Cycle Stop
    FAULT_RESET =   "FaultReset"    # Fault Reset
    START =         "Start"         # Start
    HOME =          "Home"          # Home
    ENABLE =        "Enable"        # Enable
    
    RSR1 =          "RSR1"          # Robot Service Request 1
    RSR2 =          "RSR2"          # Robot Service Request 2 (주로 시작 신호로 사용)
    
    PNS_STROBE =    "PNSStrobe"     # PNS Strobe
    PROD_START =    "ProdStart"     # Production Start
    DI43 =          "DI43"          # Loop On/Off 등
    DI44 =          "DI44"          # 예비

    # [출력] Robot -> PLC (읽는 신호) - 얘는 아직 PLC 주소가 필요할 수도 있음 (읽기 방식에 따라 다름)
    # 하지만 일단 키로 정의하고 Adapter에서 매핑하는 것이 좋음
    # 레퍼런스 코드에서는 읽기(Feedback) 관련 내용보다는 쓰기(Trigger) 위주였음.
    # 기존 코드 호환성을 위해 우선 남겨둠 (하지만 값은 확인 필요)
    
    # [중요] 완료 신호 (DO45)
    # 로봇이 명령을 수행하고 완료되었음을 알리는 Handshake 신호.
    # Rising Edge (0->1)가 발생할 때 Notification이 트리거됨.
    COMPLETE =  "MAIN.Robot1._UO1.DO45"             # 완료 신호 (기존 유지)
    
    BUSY =      "MAIN.Robot1._UO1.UO10_Busy"       # 바쁨 신호 (기존 유지)
    # PAUSED =    "MAIN.Robot1._UO1.UO04_PrgPaused"   # 일시정지
    # FAULT =     "MAIN.Robot1._UO1.UO06_Fault"       # 에러


    @property
    def path(self) -> str:
        """PLC 주소 반환"""
        return self.value
