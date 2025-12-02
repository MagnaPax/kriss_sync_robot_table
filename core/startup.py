# core/startup.py
import sys
import time
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.event_bus import EVENT_BUS
from utils.dll_loader import load_pyads_dll
from ui.splash import ConnectionSplash



class StartupManager:
    """
    애플리케이션 시작 프로세스 관리자
    
    역할:
    - 스플래시 스크린 표시
    - 필수 컴포넌트 로드 (DLL 등)
    - 로딩 상태 피드백 (성공/실패/재시도)
    - 메인 윈도우 실행 전환
    """
    
    def run(self):
        """부팅 시나리오 실행"""
        
        # 1. 스플래시 화면 표시
        splash = ConnectionSplash()
        splash.show()
        
        # 2. 필수 드라이버 로드 (DLL 로드 시도)
        if not self._load_drivers(splash):
            # 실패 처리
            splash.close()
            self._show_critical_error()
            sys.exit(1)

        # 3. 성공 처리
        splash.close()
        
        # 4. 메인 윈도우 로드 (Lazy Import)
        #    이 시점은 DLL 로드가 확실히 성공한 뒤이므로 안전함
        from ui.main_window import MainWindow
        
        window = MainWindow()
        window.show()
        
        # 여기서 window 객체를 반환하거나 유지해야 GC되지 않음 (main함수 변수에 할당됨)
        return window


    def _load_drivers(self, splash: ConnectionSplash) -> bool:
        """DLL 로드 및 접속 재시도 로직"""
        max_retries = 3
        
        for i in range(1, max_retries + 1):
            try:
                # 상태 업데이트
                splash.update_status(f"TwinCAT 접속 시도 중... ({i}/{max_retries})", i * 30)
                QApplication.processEvents()
                
                # DLL 로드 시도 (실제 로직)
                # time.sleep(0.5) # 연출용 딜레이 (필요 시 주석 해제)
                load_pyads_dll()
                
                # 성공 피드백
                splash.update_status("드라이버 로드 완료! 시스템을 시작합니다.", 100)
                EVENT_BUS.system_info.emit("TwinCAT 통신 모듈(DLL) 로드 성공")
                
                QApplication.processEvents()
                time.sleep(0.8) # 사용자가 성공 메시지를 볼 수 있게 잠시 대기
                return True

            except Exception as e:
                EVENT_BUS.ui_log_message.emit(f"드라이버 로드 시도({i}) 실패: {e}", "WARNING")
                
                if i < max_retries:
                    splash.update_status(f"로드 실패. 재시도 대기 중...", i * 30)
                    QApplication.processEvents()
                    time.sleep(1.0)
                else:
                    return False
        return False


    def _show_critical_error(self):
        """치명적 에러 팝업"""
        QMessageBox.critical(
            None, 
            "시스템 초기화 실패", 
            "TwinCAT 통신 모듈(DLL)을 로드할 수 없습니다.\n"
            "관리자에게 문의하십시오.\n\n"
            "(Tip: libs 폴더의 TcAdsDll.dll 파일을 확인하세요)"
        )
