# communication/fanuc_utils.py
"""
FANUC 로봇 통신용 유틸리티 함수 모음 (Protocol Layer)
현장에서 테스트가 끝난 원본 로직을 그대로 복사&붙여넣기(에러 발생 방지)

특징:
- 클래스가 아닌 순수 함수로 구성
- 상태를 저장하지 않음 (Stateless)
- PLC 연결 객체를 인자로 받아서 동작
"""
import time
import pyads


# ================================================ #
# TxtFileReadFANUC.py 의 함수 그대로 복사&붙여넣기
# ================================================ #

def send_bits_to_plc(plc, prefix, lower_value, high_value):
    """비트 전송"""
    for i in range(8):
        plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}l{i}', 
                        (lower_value & (1 << i)) > 0, pyads.PLCTYPE_BOOL)
        plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}h{i}', 
                        (high_value & (1 << i)) > 0, pyads.PLCTYPE_BOOL)


def send_coordinate(plc, input_val, axis_name):
    """좌표 전송 (소숫점 둘째자리까지만)"""
    # 소숫점 둘째자리로 반올림
    rounded_val = round(input_val, 2)
    scaled = int(abs(rounded_val * 100))
    send_bits_to_plc(plc, axis_name, scaled & 0xFF, scaled >> 8)
    plc.write_by_name(f'MAIN.Robot1._UI1.{axis_name}_Check', 
                    rounded_val < 0, pyads.PLCTYPE_BOOL)


def send_feed(plc, input_F):
    """Feed 전송 (소숫점 둘째자리까지만)"""
    # 소숫점 둘째자리로 반올림
    rounded_F = round(input_F, 2)
    scaled_F = int(abs(rounded_F * 100))
    for i in range(8):
        plc.write_by_name(f'MAIN.Robot1._UI1.Fl{i}', 
                        (scaled_F & (1 << i)) > 0, pyads.PLCTYPE_BOOL)
    for i in range(2):
        plc.write_by_name(f'MAIN.Robot1._UI1.Fh{i}', 
                        ((scaled_F >> 8) & (1 << i)) > 0, pyads.PLCTYPE_BOOL)


def pause_process(plc):
    print("Cycle Stop")
    plc.write_by_name('MAIN.Robot1._UI1.UI04_CycleStop', True, pyads.PLCTYPE_BOOL)
    time.sleep(0.1)
    plc.write_by_name('MAIN.Robot1._UI1.UI04_CycleStop', False, pyads.PLCTYPE_BOOL)


def resume_process(plc):
    print("Cycle Start")
    plc.write_by_name('MAIN.Robot1._UI1.UI06_Start', True, pyads.PLCTYPE_BOOL)
    time.sleep(0.1)
    plc.write_by_name('MAIN.Robot1._UI1.UI06_Start', False, pyads.PLCTYPE_BOOL)

