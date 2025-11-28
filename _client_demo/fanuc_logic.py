# fanuc_logic.py
"""
FANUC 로봇 제어를 위한 순수 로직 모듈

비트 연산, 스케일링, PLC 태그 이름 등 원본 로직과 동일하게 만듦
"""

import os
import time
from typing import Optional
from _client_demo.demo_logger import logger

# main.py에서 DLL 로드 후 pyads를 임포트합니다.
import pyads



class FanucController:
    """
    FANUC 로봇 제어를 위한 메인 컨트롤러 클래스.

    PLC 연결 상태를 지역변수로 관리(self._plc)
    """
    # IP, 포트 (상수)
    AMS_NET_ID = '5.119.154.174.1.1'
    PLC_PORT = pyads.PORT_TC3PLC1


    def __init__(self) -> None:
        # 실제 객체는 _plc(내부 변수)에 저장 (None 허용)
        self._plc: Optional['pyads.Connection'] = None

        self.is_connected: bool = False

        # 델타 계산을 위한 이전 좌표 저장소
        self.prev_coords: Optional[dict] = None

        logger.info("[FanucController] 인스턴스 생성 완료")


    # self.plc를 호출할 때마다 실행되는 '게이트키퍼' 프로퍼티
    @property
    def plc(self) -> 'pyads.Connection':
        """
        self.plc에 접근할 때마다 연결 상태를 확인하고
        연결되어 있지 않다면 즉시 에러 발생

        다른 메서드들에서 assert 검사를 없애기 위해 사용
        """
        if self._plc is None:
            raise ConnectionError("PLC가 연결되어 있지 않습니다.")
        return self._plc

    def connect_plc(self) -> tuple[bool, str]:
        """
        PLC 연결을 시도하고, 성공하면 self._plc에 연결 객체를 저장
        """
        logger.info("connect_plc 시작")

        if self.is_connected and self._plc:
            return True, f"이미 연결되어 있습니다. ({self.AMS_NET_ID})"

        try:
            # 내부 변수에 할당
            self._plc = pyads.Connection(self.AMS_NET_ID, self.PLC_PORT)
            self._plc.open()
            self._plc.read_state()  # 연결 확인 (pyads의 공식 메서드)
            self.is_connected = True
            self.prev_coords = None # 연결 시 좌표 초기화

            logger.info(f"PLC 연결 성공 ({self.AMS_NET_ID})") #
            return True, f"PLC 연결 성공 ({self.AMS_NET_ID})"
        
        except Exception as e:
            self._plc = None
            self.is_connected = False
            # 연결 실패 시 UI에 표시할 에러 메시지와 함께 False 반환
            logger.error(f"PLC 연결 실패: {e}", exc_info=True) #
            return False, f"PLC 연결 실패: {e}"

    def disconnect_plc(self):
        """PLC 연결을 해제"""
        logger.info("PLC 연결 해제 시작")

        # 연결 해제 로직은 내부 변수(_plc)를 사용 (프로퍼티 호출 시 에러 방지)
        if self._plc:
            try:
                # 루프 종료 (로봇 정지)
                # 이 신호가 꺼져야 TP 프로그램이 루프를 탈출하여 멈춤
                self._plc.write_by_name('MAIN.Robot1._UI1.DI181', False, pyads.PLCTYPE_BOOL)

                # (안전장치) 시작 트리거 신호 초기화
                # 혹시라도 켜져 있을 수 있는 RSR 신호를 강제로 False로 끔
                self._plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', False, pyads.PLCTYPE_BOOL)

                logger.info("초기화 완료")

            except Exception as e:
                logger.warning(f"RSR 신호 초기화 실패 - {e}") #

            self._plc.close()
            self._plc = None

        self.is_connected = False
        self.prev_coords = None # 기억하고 있는 좌표 초기화

        logger.info("PLC 연결이 해제되었습니다.") #



    def execute_command(self, x: float, y: float, z: float, w: float, p: float, r: float, f: float) -> tuple[bool, str]:
        """
        FANUC_Test.py의 main() 함수 로직을 단일 함수로
        
        로봇을 실제 이동시키는 RSR 신호를 발생

        인자값:
            x, y, z, w, p, r, f (float): UI에서 입력받은 모든 좌표 및 속도값

        반환값:
            tuple: (success_bool, message_str)
                - (True, "데이터 전송 및 RSR 신호 발생 완료")
                - (False, "데이터 쓰기 실패: {에러}")
        """

        if not self.is_connected:
            logger.error("명령 실행(데이터 쓰기) 실패: PLC가 연결되지 않았습니다.")
            return False, "명령 실행(데이터 쓰기) 실패: PLC가 연결되지 않았습니다."


        try:
            # 로봇이 데이터를 받을 준비가 될 때까지 계속 기다린다
            while not self.plc.read_by_name('MAIN.Robot1._UO1.DO45', pyads.PLCTYPE_BOOL):
                    time.sleep(0.005)

            # 델타값 계산
            current_coords = {'X': x, 'Y': y, 'Z': z, 'W': w, 'P': p, 'R': r}

            # 이전 값 저장
            if self.previous_coords is None:
                    # 첫 번째 데이터는 델타 계산 불가하므로 그대로(혹은 0 기준) 전송한다고 가정
                    deltas = current_coords
            else:
                # 현재값 - 이전값
                deltas = {k: current_coords[k] - self.previous_coords[k] for k in current_coords}    

            self.previous_coords = current_coords


            # --- [Send] 데이터 전송 --- #
            # Feed 전송
            self._send_feed(f)

            # 좌표 전송 (Delta)
            self._send_coordinate(deltas['X'], "X")
            self._send_coordinate(deltas['Y'], "Y")
            self._send_coordinate(deltas['Z'], "Z")
            self._send_coordinate(deltas['W'], "W")
            self._send_coordinate(deltas['P'], "P")
            self._send_coordinate(deltas['R'], "R")

            # [Post-Send] 대기
            time.sleep(0.05)
            
            return True, "데이터 전송 완료 (Delta)"

        except Exception as e:
            # 프로퍼티에서 발생한 ConnectionError도 여기서 잡힘
            logger.error(f"명령 실행(데이터 쓰기) 실패: {e}", exc_info=True)
            return False, f"명령 실행(데이터 쓰기) 실패: {e}"





    ##############################################################
    # --- [이식] 현장 코드 (TxtFileReadFANUC.py) 그대로 이식 --- #
    #        클래스의 메서드로 만들기 위해 self 만 추가          #
    ##############################################################

    def _send_bits_to_plc(self, prefix, lower_value, high_value):
        """
        하위/상위 바이트(정수)를 8개의 비트로 분해하여 PLC에 전송
        
        FANUC 로봇은 데이터를 비트 배열(BOOL[8])로 받기 때문에 이 변환이 필요

        인자값들:
            plc (pyads.Connection): 연결된 PLC 객체
            prefix (str): 태그 이름의 접두사 (예: "X", "Y", "Z"...)
            lower_value (int): 하위 8비트 (0-255)
            high_value (int): 상위 8비트 (0-255)
        """
        for i in range(8):
            # 하위 바이트 비트 전송
            self.plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}l{i}', 
                            (lower_value & (1 << i)) > 0, pyads.PLCTYPE_BOOL)
            # 상위 바이트 비트 전송
            self.plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}h{i}', 
                            (high_value & (1 << i)) > 0, pyads.PLCTYPE_BOOL)    

    def _send_coordinate(self, input_val, axis_name):
        """
        원본함수이름: send_coordinate
        """

        # 소숫점 둘째자리로 반올림
        rounded_val = round(input_val, 2)
        scaled = int(abs(rounded_val * 100))
        
        # 내부 함수 호출 시 self. 추가
        self._send_bits_to_plc(axis_name, scaled & 0xFF, scaled >> 8)
        
        self.plc.write_by_name(f'MAIN.Robot1._UI1.{axis_name}_Check', 
                        rounded_val < 0, pyads.PLCTYPE_BOOL)

    def _send_feed(self, input_F):
        """
        원본함수이름: send_feed
        """
        # 소숫점 둘째자리로 반올림
        rounded_F = round(input_F, 2)
        scaled_F = int(abs(rounded_F * 100))
        for i in range(8):
            self.plc.write_by_name(f'MAIN.Robot1._UI1.Fl{i}', 
                            (scaled_F & (1 << i)) > 0, pyads.PLCTYPE_BOOL)
        for i in range(2):
            self.plc.write_by_name(f'MAIN.Robot1._UI1.Fh{i}', 
                            ((scaled_F >> 8) & (1 << i)) > 0, pyads.PLCTYPE_BOOL)





    # ===================================
    # [제어] 프로세스 시작/정지/Loop 제어
    # ===================================
    def start_process_loop(self) -> tuple[bool, str]:
        msg = "TP Program Start"
        self._show_message(msg)

        if not self.is_connected: return False, "연결 안 됨"

        try:
            self.plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', True, pyads.PLCTYPE_BOOL)
            time.sleep(0.05)
            self.plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', False, pyads.PLCTYPE_BOOL)
            self.plc.write_by_name('MAIN.Robot1._UI1.DI181', True, pyads.PLCTYPE_BOOL)
            self.prev_coords = None
            return True, "프로세스 시작 (RSR2 Pulse, DI181 ON)"
        
        except Exception as e:
            return False, f"시작 실패: {e}"


    # --- stop_start 함수 --- #
    def send_cycle_stop(self) -> tuple[bool, str]:
        """stop_start 함수 중 '정지(S)' 부분"""
        msg = "Cycle Stop"
        self._show_message(msg)

        # UI04_CycleStop 신호를 켰다가 0.1초 뒤에 끔
        return self._pulse_signal('MAIN.Robot1._UI1.UI04_CycleStop', msg)

    def send_cycle_start(self) -> tuple[bool, str]:
        """stop_start 함수 중 '시작(G)' 부분"""
        msg = "Cycle Start"
        self._show_message(msg)

        return self._pulse_signal('MAIN.Robot1._UI1.UI06_Start', msg)


    def set_loop_signal(self, is_active: bool) -> tuple[bool, str]:
        """DI181 제어 코드"""
        if not self.is_connected: return False, "연결 안 됨"

        try:
            self.plc.write_by_name('MAIN.Robot1._UI1.DI181', is_active, pyads.PLCTYPE_BOOL)
            self._show_message(f"Loop(DI181)신호 {'루프반복(ON)' if is_active else '루프 종료(OFF)'}")
            return True, f"Loop(DI181) {'ON' if is_active else 'OFF'}"
        
        except Exception as e:
            return False, f"DI181 제어 에러: {e}"

    def _pulse_signal(self, tag_name: str, log_msg: str) -> tuple[bool, str]:
        """
        stop_start() 함수 내부의 중복되는 패턴을 함수화한 메서드

        [True -> 0.1초 대기 -> False] 패턴 반복
        """
        if not self.is_connected: return False, "연결 안 됨"

        try:
            self.plc.write_by_name(tag_name, True, pyads.PLCTYPE_BOOL)
            time.sleep(0.1)
            self.plc.write_by_name(tag_name, False, pyads.PLCTYPE_BOOL)
            return True, log_msg
        
        except Exception as e:
            return False, f"{log_msg} 실패: {e}"










    ############################
    # --- 내부 헬퍼 메서드 --- #
    ############################
    def _process_input_and_send_to_plc(self, input_val: float, axis_name: str):
        """
        좌표값과 상태(양수/음수)를 확인하여 전송하는 함수

        실수 좌표값(float)을 스케일링하고 부호를 분리하여 전송
        
        로직:
            1. (예: 15.84) -> (15.84 * 100) -> 1584 (정수)
            2. 1584 -> 하위(lower=88), 상위(high=6) 바이트로 분리
            3. send_bits_to_plc() 호출
            4. 음수일 경우 CheckBit(부호 비트)를 True로 전송

        아규먼트:
            input_val (float): UI에서 입력받은 좌표값 (예: 15.84)
            axis_name (str): 축 이름 (예: "X", "Y"...)
        """
        assert self._plc is not None, "PLC connection is not available."

        # 입력값 * 100 후 정수 변환 로직 (정밀도 소수점 2자리까지)
        scaled = round(abs(input_val * 100))

        # 16비트 정수를 8비트 하위/상위 바이트로 분리
        lower = scaled & 0xFF       # 하위 8비트 (예: 1584 & 255 = 88)
        high = scaled >> 8          # 상위 8비트 (예: 1584 >> 8 = 6)
        
        # 비트 전송 함수 호출
        self._send_bits_to_plc(axis_name, lower, high)

        # --- CheckBit(부호 비트) 전송 로직 --- #
        check_bit = True if input_val < 0 else False
        # PLC의 상태 비트 변수명은 '{축이름}_Check'
        self._plc.write_by_name(f'MAIN.Robot1._UI1.{axis_name}_Check', check_bit, pyads.PLCTYPE_BOOL)
    
    def _process_feed(self, input_F: float):
        """
        로봇 이동 속도 보내는 함수
        
        Feed(속도) 값을 스케일링하여 전송

        process_input_and_send_to_plc와 로직이 동일함
        
        인자값:
            input_F (float): UI에서 입력받은 속도값 (예: 5.0)
        """
        assert self._plc is not None, "PLC connection is not available."

        scaled_F = round(abs(input_F * 100))
        lower_F = scaled_F & 0xFF
        high_F = scaled_F >> 8

        # 하위 8비트 전송
        for i in range(8):
            is_bit_set = (lower_F & (1 << i)) > 0
            self._plc.write_by_name(f'MAIN.Robot1._UI1.Fl{i}', is_bit_set, pyads.PLCTYPE_BOOL)

        # 상위 2비트만 전송
        # high_F는 2비트만 사용            
        for i in range(2):
            is_bit_set = (high_F & (1 << i)) > 0
            self._plc.write_by_name(f'MAIN.Robot1._UI1.Fh{i}', is_bit_set, pyads.PLCTYPE_BOOL)

    def _show_message(self, msg: str):
        print(msg)
        logger.info(msg)