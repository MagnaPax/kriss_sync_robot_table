# communication/test_turntable.py

"""
TurntableOnlyExecutor 독립 실행 테스트


python -m communication.test_turntable
"""
import sys
import time
from typing import List, Dict, Any

from utils.dll_loader import load_pyads_dll
try:
    load_pyads_dll()
    print("✅ DLL 로드 성공 (Import Pre-hook)")
except Exception as e:
    print(f"⚠️ DLL 로드 실패: {e}")

from core.event_bus import EVENT_BUS
from communication.twincat_connector import TwinCATConnector
from communication.twincat_commander import TwinCATCommander
from core.log_listener import LogListener

# =========================================================
# 1. 테스트용 더미 데이터 (시퀀스 3~4개)
# =========================================================
# TurntableOnlyExecutor가 처리할 수 있는 형식 ('angle', 'velocity' 포함)
# 로봇 데이터('x', 'y'...)는 없어야 함
TEST_SEQUENCE: List[Dict[str, Any]] = [
    {'id': 1, 'angle': 90.0, 'velocity': 20.0},
    {'id': 2, 'angle': 180.0, 'velocity': 30.0},
    {'id': 3, 'angle': 270.0, 'velocity': 15.0},
    {'id': 4, 'angle': 0.0, 'velocity': 50.0},  # 원점 복귀
]

# =========================================================
# 2. 테스트 함수
# =========================================================
def run_test():
    print("=" * 60)
    print("🚀  TurntableOnlyExecutor 테스트 시작")
    print("=" * 60)

    # 1. DLL 로드
    try:
        load_pyads_dll()
        print("✅ DLL 로드 성공")
    except Exception as e:
        print(f"⚠️ DLL 로드 실패 (환경에 따라 무시 가능): {e}")

    # 2. 로그 리스너 활성화 (EventBus 로그를 콘솔에 출력)
    listener = LogListener()
    print("✅ LogListener 활성화")

    # 3. TwinCAT 연결 (Mock/Real)
    # 실제 PLC가 없으면 MockConnection이 자동으로 활성화됨 (twincat_connector 내부 로직)
    connector = TwinCATConnector()
    
    try:
        connector.connect()
        print(f"✅ TwinCAT 연결 성공 (ID: {connector.ams_net_id})")
    except Exception as e:
        print(f"❌ TwinCAT 연결 실패: {e}")
        return

    # 4. Commander 생성
    commander = TwinCATCommander(connector)
    print("✅ TwinCATCommander 초기화 완료")

    # 5. 실행 요청 (Gateway가 TurntableOnlyExecutor를 잘 선택하는지 확인)
    print(f"\n📋 테스트 데이터 전송 ({len(TEST_SEQUENCE)}건):")
    for item in TEST_SEQUENCE:
        print(f"   - {item}")
    print("-" * 60)

    # 6. 실행
    success, message = commander.execute_sequence_with_executor(TEST_SEQUENCE)

    # 7. 결과 출력
    print("\n" + "=" * 60)
    if success:
        print(f"🎉 테스트 성공: {message}")
    else:
        print(f"💥 테스트 실패: {message}")
    print("=" * 60)

    # 8. 종료 (연결 해제)
    connector.disconnect()


if __name__ == "__main__":
    run_test()
