# models/fanuc_pose_key,py.py
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
    # PLC 주소 생성 (Adapter에서 f-string 제거용)
    # ---------------------------------------------------------
    # 설명:
    # PLC와 통신할 때 숫자를 통째로 보내는 게 아니라
    # 16개의 전선(비트)으로 쪼개서 보낸다 (이진수 통신)
    # =========================================================
    
    def tag_check(self) -> str:
        """
        [음수/양수 판별용] 체크 비트의 PLC 주소 반환

        원리:
            비트로 쪼개서 보내는 숫자는 '부호 없는' 정수(절댓값)
            그래서 이 값이 양수(+)인지 음수(-)인지 알려주는 별도의 깃발(Flag)이 필요
            
        반환 예시:
            "MAIN.Robot1._UI1.X_Check" (True면 음수, False면 양수)
        """
        return f"MAIN.Robot1._UI1.{self.value}_Check"

    def tag_low_bit(self, bit_index: int) -> str:
        """
        [하위 8비트] 데이터 전송용 비트 주소 반환 (0~7번 비트)

        설명:
            큰 숫자를 16비트로 쪼갤 때 앞쪽 절반(Low Byte)을 담당
            예를들어 1234원이라는 돈을 보낼 때 34원(하위)을 먼저 보내는 것과 같음
            
        인자:
            bit_index (int): 0부터 7까지의 비트 번호
            
        반환 예시 (index=0일 때):
            "MAIN.Robot1._UI1.Xl0" (X축의 Low 바이트 0번 비트)
        """
        return f"MAIN.Robot1._UI1.{self.value}l{bit_index}"

    def tag_high_bit(self, bit_index: int) -> str:
        """
        [상위 8비트] 데이터 전송용 비트 주소 반환 (0~7번 비트)

        설명:
            큰 숫자를 16비트로 쪼갤 때, 뒤쪽 절반(High Byte)을 담당
            예를들어 1234원이라는 돈을 보낼 때 1200원(상위)을 먼저 보내는 것과 같음
            
        인자:
            bit_index (int): 0부터 7까지의 비트 번호
            
        반환 예시 (index=0일 때):
            "MAIN.Robot1._UI1.Xh0" (X축의 High 바이트 0번 비트)
        """
        return f"MAIN.Robot1._UI1.{self.value}h{bit_index}"



# =============================================================================
# 제어 신호 정의
# =============================================================================
class FanucSignal(str, Enum):
    """
    FANUC 로봇 제어를 위한 디지털 신호(Bit) 주소 모음
    """
    # [입력] Robot <- PLC (보내는 신호)
    RSR2_START = "MAIN.Robot1._UI1.UI10_RSR2"       # 작업 시작 요청 (Pulse)
    LOOP_ON    = "MAIN.Robot1._UI1.DI181"           # 연속 재생 (ON=반복)
    CYCLE_STOP = "MAIN.Robot1._UI1.UI04_CycleStop"  # 비상 정지 / 정지
    
    # [출력] Robot -> PLC (읽는 신호)
    BUSY       = "MAIN.Robot1._UO1.DO45"            # 로봇이 움직이는 중 (Busy)

    @property
    def path(self) -> str:
        """PLC 주소 반환"""
        return self.value