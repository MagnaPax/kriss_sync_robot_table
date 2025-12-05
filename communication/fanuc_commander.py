# communication/fanuc_commander.py
import time
import pyads
from typing import TYPE_CHECKING, Union
from communication.twincat_connector import TwinCATConnector


# 타입 검사기(Pylance)에게만 MockConnection의 존재를 알려줌
# 순환 참조(Circular Import) 오류를 방지하면서 타입 힌트를 제공하기 위해
if TYPE_CHECKING:
    from communication.mock_plc import MockConnection



class FanucCommander:
    """
    FANUC 로봇 통신 로직을 담당하는 Model 클래스
    원본 파일: TxtFileReadFANUC.py
    """

    def __init__(self, connector: TwinCATConnector):
        # Service에서 생성한 TwinCATConnector를 주입받음
        self.connector = connector


    @property
    def _plc(self) -> Union[pyads.Connection, 'MockConnection']:
        """Connector의 활성 핸들을 가져오는 단축 속성"""
        return self.connector.handle


    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------
    def _reset_axis_sign_bits(self):
        """양수/음수 체크 비트 초기화"""
        for axis in ['X', 'Y', 'Z', 'W', 'P', 'R']:
            self._plc.write_by_name(f'MAIN.Robot1._UI1.{axis}_Check', False, pyads.PLCTYPE_BOOL)


    # ------------------------------------------------------------------
    # 
    # ------------------------------------------------------------------
    def start_sequence_plc_signals(self):
        """RSR2 pulse + Loop start + CycleStop Off"""

        # 로봇측 체크 비트 초기화
        # 실제 작업 시작 전에 수행 (연결된 상태가 보장됨)
        self._reset_axis_sign_bits()

        plc = self._plc

        # RSR신호 Pulse
        plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', True, pyads.PLCTYPE_BOOL)
        time.sleep(0.05)

        # Loop신호(ON이면 루프 반복, OFF이면 루프 종료)
        plc.write_by_name('MAIN.Robot1._UI1.DI181', True, pyads.PLCTYPE_BOOL)

        # Cycle Stop 초기화
        plc.write_by_name('MAIN.Robot1._UI1.UI04_CycleStop', False, pyads.PLCTYPE_BOOL)

        return True, "시작 신호 전송"

    def end_sequence_plc_signals(self):
        """Sequence 종료 시 처리"""
        plc = self._plc
        plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', False, pyads.PLCTYPE_BOOL)
        plc.write_by_name('MAIN.Robot1._UI1.DI181', False, pyads.PLCTYPE_BOOL)

        return True, "정지 신호 전송"




    # ------------------------------------------------------------------
    # 비트 연산/전송 헬퍼
    # ------------------------------------------------------------------
    def send_bits_to_plc(self, prefix, lower_value, high_value):
        """
        하위/상위 바이트를 비트 단위로 쪼개서 PLC 변수에 씀
        """
        plc = self._plc
        for i in range(8):
            plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}l{i}', 
                            (lower_value & (1 << i)) > 0, pyads.PLCTYPE_BOOL)
            plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}h{i}', 
                            (high_value & (1 << i)) > 0, pyads.PLCTYPE_BOOL)

    def send_coordinate(self, val, axis):
        """
        좌표 전송 (소수점 둘째자리 반올림 후 정수 변환 -> 비트 전송)
        """
        plc = self._plc
        
        # 반올림 및 스케일링
        rounded = round(val, 2)
        scaled = int(abs(rounded * 100))

        # 비트 전송 및 음수 체크 비트 설정
        self.send_bits_to_plc(axis, scaled & 0xFF, scaled >> 8)
        plc.write_by_name(f"MAIN.Robot1._UI1.{axis}_Check",
                        rounded < 0, pyads.PLCTYPE_BOOL)

    def send_feed(self, feed_rate):
        plc = self._plc

        rounded = round(feed_rate, 2)
        scaled = int(abs(rounded * 100))

        # Fl0~7, Fh0~1 비트 전송
        for i in range(8):
            plc.write_by_name(f"MAIN.Robot1._UI1.Fl{i}",
                            (scaled & (1 << i)) > 0, pyads.PLCTYPE_BOOL)

        for i in range(2):
            plc.write_by_name(f"MAIN.Robot1._UI1.Fh{i}",
                            ((scaled >> 8) & (1 << i)) > 0, pyads.PLCTYPE_BOOL)


    # ------------------------------------------------------------------
    # 파일 처리 및 데이터 파싱
    # ------------------------------------------------------------------
    def parse_line(self, line):
        """
        문자열 한 줄을 파싱하여 dict 형태로 반환
        """
        values = line.split()
        if len(values) >= 7:
            # 원본 로직: F, X, Y, Z, W, P, R 순서로 매핑
            return {
                'F': float(values[0]), 'X': float(values[1]), 'Y': float(values[2]),
                'Z': float(values[3]), 'W': float(values[4]), 'P': float(values[5]),
                'R': float(values[6])
            }
        return None



    # ------------------------------------------------------------------
    # 핵심 시퀀스 실행 로직 이식
    # ------------------------------------------------------------------
    def _calculate_delta(self, current, previous):
        """증분계산"""
        if previous is None:
            return current.copy()
        return {key: current[key] - previous[key] for key in current.keys()}


    def execute_sequence(self, coordinates: list[dict], check_stop_func=None):
        """
        원본 main() 함수의 핵심 로직을 수행
        """
        plc = self._plc

        # 시퀀스 시작용 PLC 신호 (초기화)
        self.start_sequence_plc_signals()
        
        init_done = False   # 첫 줄 실행 트리거
        previous_coords = None


        for coordinate in coordinates:

            # 증분 계산
            delta = self._calculate_delta(coordinate, previous_coords)

            previous_coords = coordinate

            # 핸드셰이킹
            while True:
                # UI에서 정지 버튼 눌렀는지 확인
                if check_stop_func and check_stop_func():
                    raise InterruptedError("사용자에 의한 작업 중단")
                
                # DO45 (Busy) 신호 확인
                # DO45가 True이거나, 아직 첫 초기화(init_done) 전이라면 전송 수행
                busy = plc.read_by_name('MAIN.Robot1._UO1.DO45', pyads.PLCTYPE_BOOL)
                
                if (not init_done) or busy:

                    # 데이터 전송 및 로그 출력
                    self.send_feed(coordinate['F'])
                    self.send_coordinate(delta['X'], "X")
                    self.send_coordinate(delta['Y'], "Y")
                    self.send_coordinate(delta['Z'], "Z")
                    self.send_coordinate(delta['W'], "W")
                    self.send_coordinate(delta['P'], "P")
                    self.send_coordinate(delta['R'], "R")

                    init_done = True

                    break # 다음 라인으로 이동

                else:
                    # 대기 (Busy 신호가 꺼질 때까지)
                    time.sleep(0.01) # CPU 과부하 방지용 미세 딜레이 추가
                    continue

        # Sequence 정상 종료 시 처리
        self.end_sequence_plc_signals()
        return True, "시퀀스 실행 완료"            
