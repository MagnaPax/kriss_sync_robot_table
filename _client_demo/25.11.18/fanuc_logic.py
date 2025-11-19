# fanuc_logic.py
"""
FANUC 로봇 제어를 위한 순수 로직 모듈 (UI와 분리됨)

'FANUC_Test.py'의 로직을 UI에서 호출할 수 있도록 함수 형태로 재구성

비트 연산, 스케일링, PLC 태그 이름 등 원본 로직과 동일하게 만듦
"""

import os
import time
from typing import Optional
from fanuc_logger import logger

# main.py에서 DLL 로드 후 pyads를 임포트합니다.
import pyads



class FanucController:
    """
    FANUC 로봇 제어를 위한 메인 컨트롤러 클래스.

    PLC 연결 상태를 지역변수로 관리(self.plc)
    """
    # IP, 포트 (상수)
    AMS_NET_ID = '5.119.154.174.1.1'
    PLC_PORT = pyads.PORT_TC3PLC1


    def __init__(self) -> None:
        self.plc: Optional['pyads.Connection'] = None
        self.is_connected: bool = False
        logger.info("[FanucController] 인스턴스 생성 완료") #


    def connect_plc(self) -> tuple[bool, str]:
        """
        PLC 연결을 시도하고, 성공하면 self.plc에 연결 객체를 저장
        """
        logger.info("connect_plc 시작") #
        if self.is_connected and self.plc:
            return True, f"이미 연결되어 있습니다. ({self.AMS_NET_ID})"

        try:
            self.plc = pyads.Connection(self.AMS_NET_ID, self.PLC_PORT)
            self.plc.open()
            self.plc.read_state() # 연결 확인 (pyads의 공식 메서드)
            self.is_connected = True
            logger.info(f"PLC 연결 성공 ({self.AMS_NET_ID})") #
            return True, f"PLC 연결 성공 ({self.AMS_NET_ID})"
        
        except Exception as e:
            self.plc = None
            self.is_connected = False
            # 연결 실패 시 UI에 표시할 에러 메시지와 함께 False 반환
            logger.error(f"PLC 연결 실패: {e}", exc_info=True) #
            return False, f"PLC 연결 실패: {e}"


    def disconnect_plc(self):
        """PLC 연결을 해제"""
        logger.info("disconnect_plc 시작") #

        if self.plc:

            try:
                # 로봇이 멈추도록 RSR 신호를 False로 초기화
                self.plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', False, pyads.PLCTYPE_BOOL)
                logger.info("RSR 신호 False로 초기화 완료") #

            except Exception as e:
                logger.warning(f"RSR 신호 초기화 실패 - {e}") #

            self.plc.close()
            self.plc = None

        self.is_connected = False
        logger.info("PLC 연결이 해제되었습니다.") #

    def execute_command(self, x: float, y: float, z: float, w: float, p: float, r: float, f: float) -> tuple[bool, str]:
        """
        FANUC_Test.py의 main() 함수 로직을 단일 함수로 실행
        
        로봇을 실제 이동시키는 RSR 신호를 발생

        인자값:
            x, y, z, w, p, r, f (float): UI에서 입력받은 모든 좌표 및 속도값

        반환값:
            tuple: (success_bool, message_str)
                - (True, "데이터 전송 및 RSR 신호 발생 완료")
                - (False, "데이터 쓰기 실패: {에러}")
        """
        coords_str = f"X:{x}, Y:{y}, Z:{z}, W:{w}, P:{p}, R:{r}, F:{f}" #
        logger.info(f"execute_command 시작. 좌표: {coords_str}") #

        if not self.is_connected or not self.plc:
            logger.error("데이터 쓰기 실패: PLC가 연결되지 않았습니다.") #
            return False, "데이터 쓰기 실패: PLC가 연결되지 않았습니다."

        try:
            # RSR Start 신호 초기화
            #   -> 이전 명령이 남아있을 경우를 대비해 False로 초기화
            self.plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', False, pyads.PLCTYPE_BOOL)
            logger.debug("RSR 신호 OFF (초기화)") #

            # 각 축에 대해 처리하고, CheckBit와 값을 저장
            self._process_input_and_send_to_plc(x, "X")
            self._process_input_and_send_to_plc(y, "Y")
            self._process_input_and_send_to_plc(z, "Z")
            self._process_input_and_send_to_plc(w, "W")
            self._process_input_and_send_to_plc(p, "P")
            self._process_input_and_send_to_plc(r, "R")
            logger.debug("좌표(X,Y,Z,W,P,R) 값 비트 전송 완료") #

            # Feed 값 처리
            self._process_feed(f)
            logger.debug("Feed(F) 값 비트 전송 완료") #

            # RSR Start 신호 전송
            #   -> 이 신호가 True가 되면 PLC/로봇이 좌표값 읽기를 시작(로봇 동작 트리거)
            # 변수명 UI09_RSR1이 False에서 True일 때, Fanuc의 TP Program 실행
            self.plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', True, pyads.PLCTYPE_BOOL)
            logger.info("RSR 신호 ON (명령 트리거)") #
            
            # 신호가 PLC에 확실히 전달 될 시간 벌기
            time.sleep(0.5) 
            
            return True, "데이터 전송 및 RSR 신호 발생 완료"

        except Exception as e:
            # pyads 통신 중 에러 발생 시
            logger.error(f"데이터 쓰기 실패: {e}", exc_info=True) #
            return False, f"데이터 쓰기 실패: {e}"



    ############################
    # --- 내부 헬퍼 메서드 --- #
    ############################
    
    def _send_bits_to_plc(self, prefix:str, lower_value: int, high_value: int):
        """
        하위/상위 바이트(정수)를 8개의 비트로 분해하여 PLC에 전송
        
        FANUC 로봇은 데이터를 비트 배열(BOOL[8])로 받기 때문에 이 변환이 필요

        인자값들:
            plc (pyads.Connection): 연결된 PLC 객체
            prefix (str): 태그 이름의 접두사 (예: "X", "Y", "Z"...)
            lower_value (int): 하위 8비트 (0-255)
            high_value (int): 상위 8비트 (0-255)
        """
        assert self.plc is not None, "PLC connection is not available."
        # logger.debug(f"[_send_bits_to_plc] {prefix}: lower={lower_value}, high={high_value}") # 너무 상세해서 주석처리

        for i in range(8):
            # --- 하위 바이트 비트 전송 --- #
            # 하위 바이트(lower_value)의 i번째 비트가 1인지 확인            
            bit_mask = (1 << i)
            is_bit_set = (lower_value & bit_mask) > 0
            # PLC 태그에 쓰기 (예: MAIN.Robot1._UI1.Xl0, ... Xl7)
            self.plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}l{i}', is_bit_set, pyads.PLCTYPE_BOOL)

            # --- 상위 바이트 비트 전송 --- #
            # 상위 바이트(high_value)의 i번째 비트가 1인지 확인            
            bit_mask = (1 << i)
            is_bit_set = (high_value & bit_mask) > 0
            # PLC 태그에 쓰기 (예: MAIN.Robot1._UI1.Xh0, ... Xh7)
            # PLC의 변수명 '{축이름}l{0~7}'에 비트 전송            
            self.plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}h{i}', is_bit_set, pyads.PLCTYPE_BOOL)


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
        assert self.plc is not None, "PLC connection is not available."

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
        self.plc.write_by_name(f'MAIN.Robot1._UI1.{axis_name}_Check', check_bit, pyads.PLCTYPE_BOOL)
    
    def _process_feed(self, input_F: float):
        """
        로봇 이동 속도 보내는 함수
        
        Feed(속도) 값을 스케일링하여 전송

        process_input_and_send_to_plc와 로직이 동일함
        
        인자값:
            input_F (float): UI에서 입력받은 속도값 (예: 5.0)
        """
        assert self.plc is not None, "PLC connection is not available."

        scaled_F = round(abs(input_F * 100))
        lower_F = scaled_F & 0xFF
        high_F = scaled_F >> 8

        # 하위 8비트 전송
        for i in range(8):
            is_bit_set = (lower_F & (1 << i)) > 0
            self.plc.write_by_name(f'MAIN.Robot1._UI1.Fl{i}', is_bit_set, pyads.PLCTYPE_BOOL)

        # 상위 2비트만 전송
        # high_F는 2비트만 사용            
        for i in range(2):
            is_bit_set = (high_F & (1 << i)) > 0
            self.plc.write_by_name(f'MAIN.Robot1._UI1.Fh{i}', is_bit_set, pyads.PLCTYPE_BOOL)
