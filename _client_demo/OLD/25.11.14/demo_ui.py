# old/demo_ui.py
"""
FANUC 제어 로직을 위한 고객 시연용 UI (실행 파일)

- '데모 모드' 체크박스를 통해 실제 PLC 연결 없이 UI/로직 테스트 가능

- '라이브 모드' (체크 해제) 시 테스트가 완료 된 fanuc_logic.py를 그대로 호출
    - 로직에 있는 time.sleep 에 대응하기 위해(동기화작업 - 앱 멈춤 방지)
    - 모든 PLC 통신(연결, 데이터 전송)은 별도의 QThread(백그라운드 스레드)에서 실행
"""

import os, sys
import time
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QApplication, 
    QWidget, 
    QVBoxLayout, 
    QPushButton, 
    QLabel, 
    QLineEdit, 
    QTextEdit, 
    QFormLayout, 
    QGroupBox, 
    QCheckBox
)

# --- pyads 동작에 필요한 DLL 경로 설정 ---
try:
    # 현재 파일이 위치한 폴더의 절대 경로 저장
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Windows가 DLL을 검색하는 경로 목록에 이 폴더를 추가
    os.add_dll_directory(script_dir)

except AttributeError:
    pass

# --- 2. 검증된 로직 임포트 ---
import fanuc_logic

# --- 3. Mock(가짜) PLC 객체 ---
class MockPlcConnection:
    """
    '데모 모드'에서 사용할 pyads.Connection의 가짜(Mock) 객체.
    실제 PLC가 없어도 UI가 작동하는지 테스트하기 위함.
    """
    def __init__(self, ams_net_id, port):
        self._ams_net_id = ams_net_id
        self._port = port
        self.is_open = True
        self.log_messages = []
        print(f"[MOCK] 가짜 PLC 객체 생성 (대상: {ams_net_id}:{port})")

    def read_state(self):
        self.log_messages.append("[MOCK] PLC 상태 읽기 (RUN)")
        time.sleep(0.1) # 딜레이 시뮬레이션
        return "RUN"

    def write_by_name(self, tag, value, plc_type):
        # UI -> 로직 테스트의 핵심: 검증된 로직이 변환한 비트값이 출력됨
        log_msg = f"[MOCK] WRITE: {tag} = {value}"
        print(log_msg)
        self.log_messages.append(log_msg)
        time.sleep(0.01) # ADS 쓰기 딜레이 시뮬레이션

    def close(self):
        self.is_open = False
        print("[MOCK] PLC 연결 종료.")

# --- 4. 백그라운드 워커 (UI 멈춤 방지) ---
class ConnectionWorker(QObject):
    """'라이브 모드'에서 PLC 연결을 담당하는 워커 (UI 멈춤 방지)"""
    connection_finished = pyqtSignal(object, str) # (plc 객체, 상태 메시지)

    def run(self):
        # 검증된 fanuc_logic.py의 연결 함수를 호출
        plc, status_msg = fanuc_logic.connect_plc()
        self.connection_finished.emit(plc, status_msg)

class CommandWorker(QObject):
    """
    '라이브 모드'에서 좌표 전송을 담당하는 워커
    (fanuc_logic.execute_command는 time.sleep(0.5)가 있으므로 필수)
    """
    log_message = pyqtSignal(str) # 로그 메시지 전달
    command_finished = pyqtSignal()   # 작업 완료 신호

    def __init__(self, plc, coords):
        super().__init__()
        self.plc = plc
        self.coords = coords

    def run(self):
        self.log_message.emit("좌표 전송 시작... (실제 PLC 쓰기)")
        # 검증된 fanuc_logic.py의 전송 함수를 호출
        success, status_msg = fanuc_logic.execute_command(self.plc, *self.coords)
        self.log_message.emit(status_msg)
        self.command_finished.emit()

# --- 5. 메인 UI 윈도우 ---
class FanucDemoApp(QWidget):
    def __init__(self):
        super().__init__()
        self.plc = None
        self._command_thread: QThread | None = None
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("FANUC Robot Control Demo")
        self.resize(500, 600)
        layout = QVBoxLayout()

        # --- 데모 모드 스위치 ---
        self.demo_checkbox = QCheckBox("데모 모드 (PLC/로봇 없이 테스트)")
        self.demo_checkbox.setChecked(True) # 기본값: 데모 모드
        self.demo_checkbox.toggled.connect(self.on_demo_mode_toggled)
        layout.addWidget(self.demo_checkbox)

        # 1. 연결 섹션
        conn_group = QGroupBox("1. PLC 연결")
        conn_layout = QVBoxLayout()
        self.btn_connect = QPushButton(f"연결 ({fanuc_logic.AMS_NET_ID})")
        self.btn_connect.clicked.connect(self.connect_plc)
        conn_layout.addWidget(self.btn_connect)
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # 2. 입력 섹션
        input_group = QGroupBox("2. 좌표 입력 (X, Y, Z, W, P, R, F)")
        form_layout = QFormLayout()
        
        # 기본값 (Python.jpg 스크린샷 참조)
        self.inputs = {
            'X': QLineEdit("15.84"), 'Y': QLineEdit("11.87"), 'Z': QLineEdit("-1.54"),
            'W': QLineEdit("1.48"),  'P': QLineEdit("79.1"),  'R': QLineEdit("-4.35"),
            'F': QLineEdit("5")
        }
        for label, widget in self.inputs.items():
            form_layout.addRow(f"{label}:", widget)
        
        input_group.setLayout(form_layout)
        layout.addWidget(input_group)

        # 3. 실행 버튼
        self.btn_send = QPushButton("좌표 전송 및 실행 (RSR Signal)")
        self.btn_send.setFixedHeight(50)
        self.btn_send.setStyleSheet("color: darkred; font-weight: bold; font-size: 14px; background-color: #dddddd;")
        self.btn_send.clicked.connect(self.send_command)
        self.btn_send.setEnabled(False) # 연결 전엔 비활성화
        layout.addWidget(self.btn_send)

        # 4. 로그 창
        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        layout.addWidget(QLabel("로그:"))
        layout.addWidget(self.log_window)

        self.setLayout(layout)
        self.log("앱 시작. '데모 모드'가 활성화되었습니다.")
        self.log("PLC 연결 버튼을 누르세요.")

    def log(self, message: str):
        """[UI 스레드] 로그 창에 메시지를 추가하는 슬롯"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_window.append(f"[{timestamp}] {message}")
        scroll_bar = self.log_window.verticalScrollBar()
        if scroll_bar:
            scroll_bar.setValue(scroll_bar.maximum())
        QApplication.processEvents() # UI 갱신

    def on_demo_mode_toggled(self, checked):
        """데모 모드 체크박스 상태 변경 시"""
        if checked:
            self.log("데모 모드가 [ON] 되었습니다. 실제 PLC 통신을 하지 않습니다.")
        else:
            self.log("데모 모드가 [OFF] 되었습니다. 실제 PLC 연결을 시도합니다.")
        # 상태가 바뀌면 연결 초기화
        self.disconnect_plc()

    def disconnect_plc(self):
        """PLC 연결을 끊고 UI를 초기화"""
        if self.plc:
            self.plc.close()
        self.plc = None
        self.btn_connect.setText(f"연결 ({fanuc_logic.AMS_NET_ID})")
        self.btn_connect.setEnabled(True)
        self.btn_send.setEnabled(False)
        self.btn_send.setStyleSheet("color: darkred; font-weight: bold; font-size: 14px; background-color: #dddddd;")
        self.log("PLC 연결이 해제되었습니다.")

    def connect_plc(self):
        """[UI 스레드] "연결" 버튼 클릭 시 호출"""
        self.log("PLC 연결 시도 중...")
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("연결 중...")

        if self.demo_checkbox.isChecked():
            # --- 데모 모드 ---
            # 가짜 PLC 객체를 즉시 생성
            time.sleep(0.5) # 가짜 딜레이
            self.plc = MockPlcConnection(fanuc_logic.AMS_NET_ID, fanuc_logic.PLC_PORT)
            self.on_connection_finished(self.plc, "데모 모드: 가짜 PLC 연결 성공")
        else:
            # --- 라이브 모드 ---
            # 실제 연결을 위해 백그라운드 스레드 시작
            self.connection_thread = QThread()
            self.connection_worker = ConnectionWorker()
            self.connection_worker.moveToThread(self.connection_thread)
            
            self.connection_worker.connection_finished.connect(self.on_connection_finished)
            self.connection_thread.started.connect(self.connection_worker.run)
            self.connection_thread.start()

    def on_connection_finished(self, plc_instance, status_msg):
        """[UI 스레드] 연결 스레드 완료 시 호출될 슬롯"""
        self.log(status_msg)
        
        if plc_instance:
            self.plc = plc_instance # PLC 객체 저장
            self.btn_send.setEnabled(True) # 전송 버튼 활성화
            self.btn_connect.setText("연결됨 (성공)")
            self.btn_send.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #4CAF50; color: white;")
        else:
            self.btn_connect.setEnabled(True) # 재시도 가능하도록
            self.btn_connect.setText("1. PLC 연결 (실패 - 재시도)")
            
        # 스레드가 존재하면 정리
        if not self.demo_checkbox.isChecked() and hasattr(self, 'connection_thread'):
            self.connection_thread.quit()
            self.connection_thread.wait()

    def send_command(self):
        """[UI 스레드] "좌표 전송" 버튼 클릭 시"""
        if not self.plc:
            self.log("오류: PLC가 연결되지 않았습니다.")
            return

        try:
            # 1. UI에서 입력값 가져오기
            coords = [
                float(self.inputs['X'].text()), float(self.inputs['Y'].text()), float(self.inputs['Z'].text()),
                float(self.inputs['W'].text()), float(self.inputs['P'].text()), float(self.inputs['R'].text()),
                float(self.inputs['F'].text())
            ]
        except ValueError:
            self.log("오류: 모든 좌표값은 숫자여야 합니다.")
            return

        # 2. 스레드 생성 및 설정
        self.btn_send.setEnabled(False) # 중복 클릭 방지
        
        self._command_thread = QThread()
        
        if self.demo_checkbox.isChecked():
            # --- 데모 모드 ---
            # 가짜 PLC 객체를 워커에게 전달
            self.worker = CommandWorker(self.plc, coords)
        else:
            # --- 라이브 모드 ---
            # 실제 PLC 객체를 워커에게 전달
            self.worker = CommandWorker(self.plc, coords)
            
        self.worker.moveToThread(self._command_thread)
        
        # 4. 시그널/슬롯 연결
        self._command_thread.started.connect(self.worker.run)
        self.worker.command_finished.connect(self._command_thread.quit)
        self.worker.command_finished.connect(self.worker.deleteLater)
        self._command_thread.finished.connect(self._command_thread.deleteLater)
        self.worker.log_message.connect(self.log)
        self._command_thread.finished.connect(lambda: self.btn_send.setEnabled(True))
        
        # 5. 스레드 시작
        self._command_thread.start()

    def closeEvent(self, event): # type: ignore
        """UI 창을 닫을 때 자동으로 호출됩니다."""
        if self.plc:
            self.log("앱 종료. PLC 연결을 닫습니다.")
            self.plc.close()
        event.accept()

# --- 애플리케이션 실행 ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FanucDemoApp()
    window.show()
    sys.exit(app.exec())