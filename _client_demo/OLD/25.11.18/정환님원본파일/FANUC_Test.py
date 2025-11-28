import pyads
import time

try:
    plc = pyads.Connection('5.119.154.174.1.1', pyads.PORT_TC3PLC1)                             # TwinCAT 연결
    plc.open()
    plc.read_state()
    print("연결됨. Ctrl+C로 종료.")
except Exception as e:
    print(f"PLC 연결 실패: {e}")
    exit(1)


def send_bits_to_plc(plc, prefix, lower_value, high_value):                                     
    """하위/상위 비트를 PLC에 전송하는 함수."""
    for i in range(8):
        # 하위 바이트 비트 전송
        bit_mask = (1 << i)
        is_bit_set = (lower_value & bit_mask) > 0
        plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}l{i}', is_bit_set, pyads.PLCTYPE_BOOL)     # PLC의 변수명 '{축이름}l{0~7}'에 비트 전송 

        # 상위 바이트 비트 전송
        bit_mask = (1 << i)
        is_bit_set = (high_value & bit_mask) > 0
        plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}h{i}', is_bit_set, pyads.PLCTYPE_BOOL)     # PLC의 변수명 '{축이름}l{0~7}'에 비트 전송


def process_input_and_send_to_plc(input_val, axis_name):                                        # 좌표값과 상태(양수/음수)를 확인하여 전송하는 함수
    """좌표값을 받아서 PLC로 처리하는 함수"""
    scaled = round(abs(input_val * 100))                                                        # EtherNet/IP의 I/O는 정수만 송수신 가능하여 스케일 후 전송, 부동소수점 오차 방지를 위해 round 사용
    lower = scaled & 0xFF
    high = scaled >> 8
    
    send_bits_to_plc(plc, axis_name, lower, high)

    # CheckBit 전송
    check_bit = True if input_val < 0 else False                                                # 상태 비트(음수이면 True, 양수이면 False)
    plc.write_by_name(f'MAIN.Robot1._UI1.{axis_name}_Check', check_bit, pyads.PLCTYPE_BOOL)     # PLC의 상태 비트 변수명은 '{축이름}_Check'

    return check_bit


def process_feed(input_F):                                                                      # 로봇 이동 속도 보내는 함수
    """Feed 값 처리"""
    scaled_F = round(abs(input_F * 100))
    lower_F = scaled_F & 0xFF
    high_F = scaled_F >> 8
    for i in range(8):
        is_bit_set = (lower_F & (1 << i)) > 0
        plc.write_by_name(f'MAIN.Robot1._UI1.Fl{i}', is_bit_set, pyads.PLCTYPE_BOOL)            # PLC의 변수명 'Fl{0~7}'에 비트 전송
    
    for i in range(2):  # high_F는 2비트만 사용
        is_bit_set = (high_F & (1 << i)) > 0
        plc.write_by_name(f'MAIN.Robot1._UI1.Fh{i}', is_bit_set, pyads.PLCTYPE_BOOL)            # PLC의 변수명 'Fh{0~1}'에 비트 전송


def main():
    try:
        while True:
            try:
                # RSR Start 신호 초기화
                plc.write_by_name('MAIN.Robot1._UI.UI09_RSR1', False, pyads.PLCTYPE_BOOL)

                # 사용자로부터 좌표 값 받기
                input_X = float(input("이동할 좌표(X, mm): "))
                input_Y = float(input('이동할 좌표(Y, mm): '))
                input_Z = float(input('이동할 좌표(Z, mm): '))
                input_W = float(input("이동할 좌표(W, deg): "))
                input_P = float(input('이동할 좌표(P, deg): '))
                input_R = float(input('이동할 좌표(R, deg): '))
                input_F = float(input('이동 속도(Feed): '))

                # 각 축에 대해 처리하고, CheckBit와 값을 저장
                process_input_and_send_to_plc(input_X, "X")
                process_input_and_send_to_plc(input_Y, "Y")
                process_input_and_send_to_plc(input_Z, "Z")
                process_input_and_send_to_plc(input_W, "W")
                process_input_and_send_to_plc(input_P, "P")
                process_input_and_send_to_plc(input_R, "R")

                # Feed 값 처리
                process_feed(input_F)

                # RSR Start 신호 전송
                plc.write_by_name('MAIN.Robot1._UI1.UI09_RSR1', True, pyads.PLCTYPE_BOOL)       # 변수명 UI09_RSR1이 False에서 True일 때, Fanuc의 TP Program 실행
                time.sleep(0.5)

            except Exception as e:
                print(f"데이터 쓰기 실패: {e}")

    except KeyboardInterrupt:
        print("\n사용자에 의해 종료됨.")

if __name__ == '__main__':
    main()
