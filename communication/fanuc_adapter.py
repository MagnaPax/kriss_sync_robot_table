# communication/fanuc_adapter.py
import time
import pyads
from typing import TYPE_CHECKING, Union
from communication.twincat_connector import TwinCATConnector
from models.fanuc_pose_key import FANUCPoseKey, FanucSignal


# 실제 런타임에는 실행 안 됨
# 타입 검사기(Pylance)에게만 MockConnection의 존재를 알려줌
# 순환 참조(Circular Import) 오류를 방지하면서 타입 힌트를 제공하기 위해
if TYPE_CHECKING:
    from communication.mock_plc import MockConnection



class FanucAdapter:
    """
    FANUC 로봇 통신 로직을 담당하는 Model(도메인 + 프로토콜) 레이어
        실제 로봇 인터페이스를 아는 곳
        데이터 변환(Float -> Int -> Bit)과 전송(Write) 작업 수행

        FanucAdapter: 손과 발
            - 시키는 대로 비트(send_bits)를 쏘고, 상태(read_busy)를 읽기만 한다
        TwinCAT Commander: 뇌 
            - 로직(루프, 델타 계산, 핸드셰이킹 등) 담당
    """

    def __init__(self, connector: TwinCATConnector):
        # 지갑(Connector)을 받아서 저장
        self.connector = connector


    @property
    def _plc(self) -> Union[pyads.Connection, 'MockConnection']:
        """
        Connector의 활성 핸들을 가져오는 단축 속성

        사용 예:
            self._plc : TwinCATConnector.handle 실행돼서 _twincat(트윈캣 핸들) 반환됨
        """
        return self.connector.handle


    # ==========================================================================
    # 1. 제어 신호 (깃발 흔들기)
    # --------------------------------------------------------------------------
    # 로봇에게 "준비해", "시작해", "멈춰" 같은 상태 신호를 보낸다
    # ==========================================================================

    def set_initial_signals(self):
        """
        [시퀀스 시작 전 준비]
        로봇이 움직이기 전에 필요한 모든 스위치를 초기 위치로 돌려놓습니다.
        """
        plc = self._plc

        # RSR(Robot Service Request) 신호 켜기
        # "로봇아, 작업 요청이 들어왔어!"라고 알리는 초인종 같은 신호
        plc.write_by_name(FanucSignal.RSR2_START.path, True, pyads.PLCTYPE_BOOL)
        
        # 신호가 확실히 전달되도록 아주 잠깐 누르고 있는다 (0.05초)
        time.sleep(0.05) 

        # Loop 신호 켜기
        # "이 작업은 연속으로 계속될 거야"라고 알림(Ture: 루프 반복, False: 루프 종료)
        plc.write_by_name(FanucSignal.LOOP_ON.path, True, pyads.PLCTYPE_BOOL)

        # 비상 정지(Cycle Stop) 해제
        plc.write_by_name(FanucSignal.CYCLE_STOP.path, False, pyads.PLCTYPE_BOOL)

        # 모든 축의 방향(양수/음수) 깃발 내리기
        # 모두(X,Y,Z,W,P,R) 초기화
        for key in FANUCPoseKey:
            # 예: "MAIN.Robot1._UI1.X_Check" = False (양수 상태로 초기화)
            plc.write_by_name(key.tag_check(), False, pyads.PLCTYPE_BOOL)


    def set_finish_signals(self):
        """[시퀀스 종료] 모든 작업을 마치고 신호를 끈다"""
        plc = self._plc
        # 요청 신호 끄기
        plc.write_by_name(FanucSignal.RSR2_START.path, False, pyads.PLCTYPE_BOOL)
        # 반복 신호 끄기
        plc.write_by_name(FanucSignal.LOOP_ON.path, False, pyads.PLCTYPE_BOOL)


    def set_emergency_stop(self):
        """[비상 정지] 즉시 멈춤 신호를 보낸다"""
        plc = self._plc
        # 일단 작업 신호들은 다 끄고
        self.set_finish_signals()
        # 비상정지(Cycle Stop) 실행
        plc.write_by_name(FanucSignal.CYCLE_STOP.path, True, pyads.PLCTYPE_BOOL)


    # ==========================================================================
    # 2. 데이터 전송 (좌표값 보내기)
    # --------------------------------------------------------------------------
    # 컴퓨터의 실수(Float, 12.34)를 PLC가 이해하는 정수 비트 배열로 변환
    # ==========================================================================

    def send_data_packet(self, feed_rate: float, delta: dict):
        """
        [데이터 패킷 전송]
        속도(Feed)와 6개 축의 이동량(Delta)을 한 번에 전송

        Args:
            feed_rate (float): 이동 속도
            delta (dict): {'x': 10.0, 'y': -5.5 ...} 형태의 증분값 딕셔너리
                        (주의: 키는 소문자일 수도 있고 대문자일 수도 있음. model_key로 해결)
        """
        # 1. 속도 전송
        self._send_feed(feed_rate)

        # 2. 6개 축 좌표 전송
        # FANUCPoseKey(X, Y, Z...)를 하나씩 꺼내서 반복
        for key in FANUCPoseKey:
            # 딕셔너리에서 값 찾기
            # key.model_key는 "x", "y" 같은 소문자 키를 반환
            # 딕셔너리에 없으면 기본값 0.0을 사용
            val = delta.get(key.model_key, 0.0)
            
            # 단일 축 전송 헬퍼 호출
            self._send_coordinate(val, key)


    def _send_coordinate(self, val: float, key: FANUCPoseKey):
        """
        [핵심] 단일 축 좌표 변환 및 전송 로직

        원리:
            PLC는 소수점(float)을 직접 받지 못한다
            그래서 12.34를 보내고 싶으면 -> 1234 (정수)로 만들어서 보내야 된다
            그리고 '이거 음수 값이다'라는 깃발(_Check)을 따로 든다
        """
        plc = self._plc

        # 1. 반올림: 소수점 2자리까지만 유효 (예: 12.3456 -> 12.35)
        rounded = round(val, 2)
        
        # 2. 정수화 (Scaling): 100을 곱해서 소수점을 없앰 (예: 12.35 -> 1235)
        #    abs()를 써서 부호(-)를 떼고 절댓값만 취함
        scaled_int = int(abs(rounded * 100))
        
        # 3. 비트 쪼개기 및 전송
        #    scaled_int라는 큰 숫자를 16개의 작은 전선으로 나누어 보냄
        #    & 0xFF : 하위 8비트 추출
        #    >> 8   : 상위 8비트 추출
        self._send_bits(key, scaled_int & 0xFF, scaled_int >> 8)
        
        # 4. 부호(Sign) 전송
        #    값이 0보다 작으면 Check 비트를 True(ON)로 켬
        #    key.tag_check() -> "MAIN.Robot1._UI1.X_Check"
        plc.write_by_name(key.tag_check(), rounded < 0, pyads.PLCTYPE_BOOL)


    def _send_bits(self, key: FANUCPoseKey, lower_byte: int, high_byte: int):
        """
        [비트 단위 전송]
        숫자를 0과 1의 전기 신호로 바꾸어 16개의 스위치(비트)를 켠다

        Args:
            key: 어느 축인지 (X, Y...)
            lower_byte: 하위 8비트 숫자 (0~255)
            high_byte: 상위 8비트 숫자 (0~255)
        """
        plc = self._plc
        
        # 0번부터 7번 비트까지 총 8번 반복
        for i in range(8):
            # -----------------------------------------------------
            # 비트 연산 설명 (Shift & AND)
            # (1 << i) : 1을 i칸만큼 왼쪽으로 밈. (예: i=2면 00000100)
            # &        : 둘 다 1일 때만 1. (마스크 씌우기)
            # > 0      : 결과가 0보다 크면 해당 자리에 1이 있다는 뜻
            # -----------------------------------------------------

            # 하위 비트 전송 (예: Xl0, Xl1 ...)
            # FANUCPoseKey가 주소("MAIN...Xl0")를 만들어줌
            plc.write_by_name(
                key.tag_low_bit(i), 
                (lower_byte & (1 << i)) > 0, 
                pyads.PLCTYPE_BOOL
            )
            
            # 상위 비트 전송 (예: Xh0, Xh1 ...)
            plc.write_by_name(
                key.tag_high_bit(i), 
                (high_byte & (1 << i)) > 0, 
                pyads.PLCTYPE_BOOL
            )

    def _send_feed(self, feed_rate: float):
        """
        [속도 전송] 좌표 전송과 원리는 같지만, 축 이름 대신 'F'를 사용
        """
        plc = self._plc

        rounded = round(feed_rate, 2)
        scaled = int(abs(rounded * 100))

        # Feed는 Enum에 없으므로 여기서 직접 주소를 조합 (Fl0~Fl7, Fh0~Fh1)
        # 로봇측 프로토콜: F는 10비트(하위8 + 상위2)만 사용함
        
        # 하위 8비트 (Fl0 ~ Fl7)
        for i in range(8):
            plc.write_by_name(f"MAIN.Robot1._UI1.Fl{i}",
                            (scaled & (1 << i)) > 0, pyads.PLCTYPE_BOOL)

        # 상위 2비트 (Fh0 ~ Fh1) -> 2번만 반복
        for i in range(2):
            plc.write_by_name(f"MAIN.Robot1._UI1.Fh{i}",
                            ((scaled >> 8) & (1 << i)) > 0, pyads.PLCTYPE_BOOL)


    # ==========================================================================
    # 3. 상태 읽기 (로봇의 대답 듣기)
    # --------------------------------------------------------------------------
    # 로봇이 현재 바쁜지(Busy) 확인합니다.
    # ==========================================================================

    def read_busy_signal(self) -> bool:
        """
        [Busy 신호 확인]
        DO45 (Digital Output 45번) 핀을 확인한다
        
        반환:
            True: 이전 명령을 접수해서 현재 로봇이 움직이고 있다
                ⚠️ 하지만 현재 input register 는 비어있기 때문에 다음 명령 받을 수 있다!!!
            False: 안 바쁘다 (다음 명령 줘)
        """
        return bool(self._plc.read_by_name(FanucSignal.BUSY.path, pyads.PLCTYPE_BOOL))
