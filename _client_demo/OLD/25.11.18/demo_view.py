# view.py
"""
FANUC 제어 로직을 위한 고객 시연용 UI (실행 파일)
- FanucController 클래스를 사용하여 PLC와 통신
- '데모 모드' 지원
"""
import sys
import time
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, 
    QLabel, QLineEdit, QTextEdit, QFormLayout, QGroupBox, QCheckBox
)
from viewmodel import FanucViewModel



class FanucDemoApp(QWidget):
    def __init__(self, viewmodel: FanucViewModel):
        super().__init__()
        self.vm = viewmodel
        self.init_ui()
        self._connect_events()

    def init_ui(self):
        """UI 위젯 생성 및 배치"""
        self.setWindowTitle("FANUC Robot Control Demo")
        self.resize(500, 600)
        layout = QVBoxLayout()

        # --- 데모 모드 스위치 ---
        self.demo_checkbox = QCheckBox("데모 모드 (PLC/로봇 없이 테스트)")
        self.demo_checkbox.setChecked(True)
        layout.addWidget(self.demo_checkbox)

        # 연결 섹션
        conn_group = QGroupBox("1. PLC 연결")
        conn_layout = QVBoxLayout()
        self.btn_connect = QPushButton("연결") # VM이 텍스트를 설정할 것
        conn_layout.addWidget(self.btn_connect)
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # 입력 섹션
        input_group = QGroupBox("2. 좌표 입력 (X, Y, Z, W, P, R, F)")
        form_layout = QFormLayout()
        
        # 기본값
        self.inputs = {
            'X': QLineEdit("15.84"), 'Y': QLineEdit("11.87"), 'Z': QLineEdit("-1.54"),
            'W': QLineEdit("1.48"),  'P': QLineEdit("79.1"),  'R': QLineEdit("-4.35"),
            'F': QLineEdit("5")
        }
        for label, widget in self.inputs.items():
            form_layout.addRow(f"{label}:", widget)
        
        input_group.setLayout(form_layout)
        layout.addWidget(input_group)

        # 실행 버튼
        self.btn_send = QPushButton("좌표 전송 및 실행 (RSR Signal)")
        self.btn_send.setFixedHeight(50)
        self.btn_send.setEnabled(False) # VM이 활성화할 것
        layout.addWidget(self.btn_send)

        # 로그 창
        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        layout.addWidget(QLabel("로그:"))
        layout.addWidget(self.log_window)

        self.setLayout(layout)

    def _connect_events(self):
        """View의 이벤트(버튼 클릭)를 ViewModel의 슬롯(메서드)에 연결 (명령)"""
        self.demo_checkbox.toggled.connect(self.vm.set_demo_mode)
        self.btn_connect.clicked.connect(self.vm.connect_plc)
        self.btn_send.clicked.connect(self.on_send_button_clicked)

        """ViewModel의 시그널을 View의 슬롯(메서드)에 연결 (옵저버)"""
        self.vm.log_updated.connect(self.log)
        self.vm.connection_changed.connect(self.on_connection_changed)

    @pyqtSlot()
    def on_send_button_clicked(self):
        """
        '전송' 버튼 클릭 시, View는 데이터를 dict로 모아서 VM에 전달
        """
        coords_data = {label: widget.text() for label, widget in self.inputs.items()}
        self.vm.send_command(coords_data)

    @pyqtSlot(str)
    def log(self, message: str):
        """VM이 보낸 로그 메시지를 UI에 표시"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_window.append(f"[{timestamp}] {message}")
        scroll_bar = self.log_window.verticalScrollBar()
        if scroll_bar:
            scroll_bar.setValue(scroll_bar.maximum())

    @pyqtSlot(bool, str)
    def on_connection_changed(self, is_connected: bool, status_msg: str):
        """VM으로부터 받은 연결 상태로 UI 갱신"""
        self.btn_send.setEnabled(is_connected)
        
        if is_connected:
            self.btn_connect.setText("연결됨 (성공)")
            self.btn_connect.setEnabled(False)
            self.btn_send.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #4CAF50; color: white;")
        else:
            self.btn_connect.setText("연결")
            self.btn_connect.setEnabled(True)
            self.btn_send.setStyleSheet("color: darkred; font-weight: bold; font-size: 14px; background-color: #dddddd;")

    def closeEvent(self, event): # type: ignore
        """UI 창을 닫을 때 VM에게 알림"""
        self.vm.disconnect_plc()
        event.accept()