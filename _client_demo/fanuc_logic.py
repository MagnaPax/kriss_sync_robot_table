# fanuc_logic.py
"""
FANUC 로봇 제어를 위한 순수 로직 모듈 (UI와 분리됨)

'FANUC_Test.py'의 로직을 UI에서 호출할 수 있도록 함수 형태로 재구성

비트 연산, 스케일링, PLC 태그 이름 등 원본 로직과 동일하게 만듦
"""

import pyads
import time

# IP, 포트 (상수)
AMS_NET_ID = '5.119.154.174.1.1'
PLC_PORT = pyads.PORT_TC3PLC1

def connect_plc():
    """
    PLC 연결을 시도하고 연결 객체를 반환

    반환:
        tuple: (plc값, 메세지)
            - 성공 시: (pyads.Connection 객체, "PLC 연결 성공 (5.119.154.174.1.1)")
            - 실패 시: (None, "PLC 연결 실패: {에러}")
    """
    try:
        plc = pyads.Connection(AMS_NET_ID, PLC_PORT)
        plc.open()
        plc.read_state() # 연결 확인용 (pyads의 공식 메서드)
        return plc, f"PLC 연결 성공 ({AMS_NET_ID})"
    except Exception as e:
        # 연결 실패 시 UI에 표시할 에러 메시지와 함께 None 반환
        return None, f"PLC 연결 실패: {e}"

def send_bits_to_plc(plc: pyads.Connection, prefix: str, lower_value: int, high_value: int):
    """
    [동작 확인됨] 하위/상위 바이트(정수)를 8개의 비트로 분해하여 PLC에 전송
    
    FANUC 로봇은 데이터를 비트 배열(BOOL[8])로 받기 때문에 이 변환이 필요

    인자값들:
        plc (pyads.Connection): 연결된 PLC 객체
        prefix (str): 태그 이름의 접두사 (예: "X", "Y", "Z"...)
        lower_value (int): 하위 8비트 (0-255)
        high_value (int): 상위 8비트 (0-255)
    """
    for i in range(8):
        # 1. 하위 바이트(lower_value)의 i번째 비트가 1인지 확인
        bit_mask = (1 << i)
        is_bit_set = (lower_value & bit_mask) > 0
        # PLC 태그에 쓰기 (예: MAIN.Robot1._UI1.Xl0, ... Xl7)
        plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}l{i}', is_bit_set, pyads.PLCTYPE_BOOL)

        # 2. 상위 바이트(high_value)의 i번째 비트가 1인지 확인
        bit_mask = (1 << i)
        is_bit_set = (high_value & bit_mask) > 0
        # PLC 태그에 쓰기 (예: MAIN.Robot1._UI1.Xh0, ... Xh7)
        plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}h{i}', is_bit_set, pyads.PLCTYPE_BOOL)

def process_input_and_send_to_plc(plc: pyads.Connection, input_val: float, axis_name: str):
    """
    [동작 확인됨] 실수 좌표값(float)을 스케일링하고 부호를 분리하여 전송
    
    로직:
        1. (예: 15.84) -> (15.84 * 100) -> 1584 (정수)
        2. 1584 -> 하위(lower=88), 상위(high=6) 바이트로 분리
        3. send_bits_to_plc() 호출
        4. 음수일 경우 CheckBit(부호 비트)를 True로 전송

    아규먼트:
        plc (pyads.Connection): 연결된 PLC 객체
        input_val (float): UI에서 입력받은 좌표값 (예: 15.84)
        axis_name (str): 축 이름 (예: "X", "Y"...)
    """
    # 입력값 * 100 후 정수 변환 로직 (정밀도 소수점 2자리까지)
    scaled = int(abs(input_val * 100))
    
    # 16비트 정수를 8비트 하위/상위 바이트로 분리
    lower = scaled & 0xFF        # 하위 8비트 (예: 1584 & 255 = 88)
    high = scaled >> 8           # 상위 8비트 (예: 1584 >> 8 = 6)
    
    # 비트 전송 함수 호출
    send_bits_to_plc(plc, axis_name, lower, high)

    # CheckBit(부호 비트) 전송 로직
    check_bit = True if input_val < 0 else False
    plc.write_by_name(f'MAIN.Robot1._UI1.{axis_name}_Check', check_bit, pyads.PLCTYPE_BOOL)

def process_feed(plc: pyads.Connection, input_F: float):
    """
    [동작 확인됨] Feed(속도) 값을 스케일링하여 전송

    process_input_and_send_to_plc와 로직이 동일함
    
    인자값:
        plc (pyads.Connection): 연결된 PLC 객체
        input_F (float): UI에서 입력받은 속도값 (예: 5.0)
    """
    scaled_F = round(abs(input_F * 100)) # 반올림
    lower_F = scaled_F & 0xFF
    high_F = scaled_F >> 8
    
    # 하위 8비트 전송
    for i in range(8):
        is_bit_set = (lower_F & (1 << i)) > 0
        plc.write_by_name(f'MAIN.Robot1._UI1.Fl{i}', is_bit_set, pyads.PLCTYPE_BOOL)
    
    # 상위 2비트만 전송 (검증된 로직)
    for i in range(2):
        is_bit_set = (high_F & (1 << i)) > 0
        plc.write_by_name(f'MAIN.Robot1._UI1.Fh{i}', is_bit_set, pyads.PLCTYPE_BOOL)

def execute_command(plc: pyads.Connection, x: float, y: float, z: float, w: float, p: float, r: float, f: float) -> tuple[bool, str]:
    """
    [동작 확인] FANUC_Test.py의 main() 함수 로직을 단일 함수로 실행
    
    로봇을 실제 이동시키는 RSR 신호를 발생

    인자값:
        plc (pyads.Connection): 연결된 PLC 객체
        x, y, z, w, p, r, f (float): UI에서 입력받은 모든 좌표 및 속도값

    반환값:
        tuple: (success_bool, message_str)
            - (True, "데이터 전송 및 RSR 신호 발생 완료")
            - (False, "데이터 쓰기 실패: {에러}")
    """
    try:
        # 1. RSR Start 신호 초기화 (False)
        #    이전 명령이 남아있을 경우를 대비해 False로 초기화
        plc.write_by_name('MAIN.Robot1._UI.UI09_RSR1', False, pyads.PLCTYPE_BOOL)

        # 2. 각 축 데이터 처리 및 전송
        process_input_and_send_to_plc(plc, x, "X")
        process_input_and_send_to_plc(plc, y, "Y")
        process_input_and_send_to_plc(plc, z, "Z")
        process_input_and_send_to_plc(plc, w, "W")
        process_input_and_send_to_plc(plc, p, "P")
        process_input_and_send_to_plc(plc, r, "R")

        # 3. Feed 처리
        process_feed(plc, f)

        # 4. RSR Start 신호 전송 (True) -> 로봇 동작 트리거
        #    이 신호가 True가 되면 PLC/로봇이 좌표값 읽기를 시작
        plc.write_by_name('MAIN.Robot1._UI1.UI09_RSR1', True, pyads.PLCTYPE_BOOL)
        
        # 신호가 PLC에 확실히 전달될 시간 벌기
        time.sleep(0.5) 
        
        return True, "데이터 전송 및 RSR 신호 발생 완료"

    except Exception as e:
        # pyads 통신 중 에러 발생 시
        return False, f"데이터 쓰기 실패: {e}"