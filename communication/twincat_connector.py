# communication/twincat_connector.py
"""
TwinCAT Connector
역할: TwinCAT ADS 프로토콜 연결 생명주기 관리 (Model Layer)

특징:
- pyads.Connection 객체 관리
- 연결/해제 로직 수행
- 실패 시 예외(Exception)를 발생시켜 호출부(Service)에 알림


-------------------------------------------------------------------------
** ADS (Automation Device Specification) 프로토콜 **
    - 개발사: Beckhoff Automation
    - 기본 통신 방식: TCP/IP
    - 활용 분야: TwinCAT 시스템 내의 PLC, NC, HMI 간 데이터 교환


** TwinCAT **
    - PC 기반 제어 - PLC 아님
    - PLC, 모션 제어, HMI(Human-Machine Interface)
    - XAE : PC에 설치되는 제어 프로그램 개발 도구
    - XAR : 실시간 제어 실행을 담당하는 런타임 시스템    
"""
import pyads
from typing import Optional
from core.settings import SETTINGS




class TwinCATConnector:
    def __init__(self):
        self._plc: Optional[pyads.Connection] = None
        self._is_connected: bool = False
        
        # 연결 설정 읽기 - settings.ini 에 저장된 데이터 사용
        self.ams_net_id = SETTINGS.plc.ams_net_id
        self.port = SETTINGS.plc.port


    @property
    def handle(self) -> pyads.Connection:
        """
        연결된 pyads 객체 반환 (Commander가 사용)
        """
        if self._plc is None or not self._is_connected:
            raise ConnectionError("PLC 연결이 초기화되지 않았거나 끊어졌습니다.")
        return self._plc


    @property
    def is_connected(self) -> bool:
        return self._is_connected


    def connect(self) -> None:
        """
        TwinCAT 연결 시도
        
        Raises:
            ConnectionError: 연결 실패 시 상세 원인과 함께 발생
        """
        if self._is_connected:
            return

        try:
            # 1. Connection 객체 생성
            self._plc = pyads.Connection(self.ams_net_id, self.port)
            
            # 2. 포트 열기
            self._plc.open()
            
            # 3. 검증 (실제 통신 확인)
            self._plc.read_state() 

            self._is_connected = True

        except Exception as e:
            self._plc = None
            self._is_connected = False
            # 예외를 래핑하여 호출부(Service)로 던짐
            raise ConnectionError(f"TwinCAT 연결 실패 ({self.ams_net_id}:{self.port}) - {e}") from e


    def disconnect(self) -> None:
        """연결 해제"""
        if self._plc:
            try:
                self._plc.close()
            except Exception:
                pass # 해제 중 에러는 무시
            finally:
                self._plc = None
        
        self._is_connected = False


    def check_connection(self) -> bool:
        """
        연결 상태 확인 (Ping)

        주기적으로 호출되어 연결이 살아있는지 확인
        예외를 던지지 않고 True/False만 반환
        (상태 체크용이므로)
        """

        # 1. 이미 연결 끊김 상태면 False 반환
        if not self._plc or not self._is_connected:
            return False
            
        try:
            # 2. 상태 읽기 시도 (Ping)
            self._plc.read_state()
            return True
            
        except Exception:
            # 3. 연결 상태 읽기 실패 시: 물리적 연결이 끊어진 것으로 간주하고 정리 수행
            # (로그는 Service에서 처리하므로 여기선 조용히 정리만 함)
            self.disconnect()
            return False
