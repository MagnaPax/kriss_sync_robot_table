# demo_view.py
"""
FANUC 제어 로직을 위한 고객 시연용 UI (실행 파일)
- FanucController 클래스를 사용하여 PLC와 통신
- '데모 모드' 지원
"""
import sys
import time
from pathlib import Path
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, 
    QLabel, QLineEdit, QTextEdit, QFormLayout, QGroupBox, QCheckBox, QFileDialog
)
from _client_demo.demo_viewmodel import FanucViewModel



class FanucDemoApp(QWidget):
    def __init__(self, viewmodel: FanucViewModel):
        super().__init__()
        self.vm = viewmodel
        self.init_ui()
        self._bind_events()

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


        file_load_group = QGroupBox("2. 파일 로드")
        file_load_layout = QVBoxLayout()

        self.btn_load_file = QPushButton("시퀀스 파일 불러오기")
        file_load_layout.addWidget(self.btn_load_file)
        file_load_group.setLayout(file_load_layout)
        layout.addWidget(file_load_group)

        # 입력 섹션
        form_input_group = QGroupBox("3. 좌표 입력 (X, Y, Z, W, P, R, F)")
        form_layout = QFormLayout()

        
        # 기본값
        self.inputs = {
            'X': QLineEdit("15.84"), 'Y': QLineEdit("11.87"), 'Z': QLineEdit("-1.54"),
            'W': QLineEdit("1.48"),  'P': QLineEdit("79.1"),  'R': QLineEdit("-4.35"),
            'F': QLineEdit("5")
        }
        for label, widget in self.inputs.items():
            form_layout.addRow(f"{label}:", widget)
        
        form_input_group.setLayout(form_layout)
        form_input_group.setEnabled(True) # 파일이 읽히면 비활성화
        layout.addWidget(form_input_group)

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

    def _bind_events(self):
        """
        [View ➡️ ViewModel]
        View의 이벤트(버튼 클릭)를 ViewModel의 슬롯(메서드)에 연결 (명령)
        """
        self.demo_checkbox.toggled.connect(self.vm.set_demo_mode)   # 데모 모드 체크박스
        self.btn_connect.clicked.connect(self.vm.connect_plc)       # 연결 버튼
        self.btn_load_file.clicked.connect(self._handle_load_file_button_clicked)   # 파일 로드 버튼
        self.btn_send.clicked.connect(self._handle_send_button_clicked) # 좌표 전송 및 실행 버튼

        """
        View ⬅️ ViewModel
        ViewModel의 시그널을 View의 슬롯(메서드)에 연결 (옵저버)
        """
        self.vm.log_updated.connect(self.log)   # 뷰의 로그창에 보여질 메세지
        self.vm.connection_changed.connect(self._handle_connection_changed) # 연결 상태
        self.vm.sequence_data.connect(self._handle_sequence_data)   # 시퀀스 데이터



    ##############################################################
    # -- VM의 메서드를 호출하기 전 View 에서 해야 되는 작업들 -- #
    ##############################################################
    @pyqtSlot()
    def _handle_load_file_button_clicked(self):
        """ 
        '시퀀스 파일 불러오기' 버튼이 클릭되면 파일을 선택할 수 있는 다이얼로그를 표시

        선택된 파일의 경로를 VM에 전달
        """
        # QFileDialog를 사용하여 문자열 경로 획득
        file_path_str, _ = QFileDialog.getOpenFileName(
            self, # 부모 위젯
            "좌표 시퀀스 파일 선택", # 다이얼로그 제목
            "", # 기본 디렉토리
            "텍스트 파일 (*.txt);;모든 파일 (*.*)" # 파일 필터
        )
        
        if file_path_str:
            # 문자열 경로를 pathlib.Path 객체로 변환
            file_path_obj = Path(file_path_str)
            
            self.log(f"파일 선택됨: {file_path_obj}")
            
            # Path 객체를 VM의 슬롯으로 전달
            self.vm.load_coordinate_sequence_file(file_path_obj)

        else:
            self.log("파일 선택이 취소되었습니다.")

    @pyqtSlot()
    def _handle_send_button_clicked(self):
        """
        '전송' 버튼 클릭 시, View는 데이터를 dict로 모아서 VM에 전달
        """
        # 파일이 로드되어(큐가 차 있고), 체크박스 등이 '파일 모드'라면
        # 혹은 뷰모델이 알아서 판단하게 위임

        if self.vm.has_sequence_data(): # 큐에 데이터가 있으면 자동 실행 우선
            self.vm.start_auto_sequence()
        else:
            # 데이터 없으면 기존처럼 입력창 값으로 수동 실행
            coords_data = {label: widget.text() for label, widget in self.inputs.items()}
            self.vm.send_command(coords_data)



    ###################################
    # -- VM 에서 넘어온 데이터 처리-- #
    ###################################
    @pyqtSlot(str)
    def log(self, message: str):
        """로그 메시지를 UI에 표시"""

        timestamp = time.strftime("%H:%M:%S")
        self.log_window.append(f"[{timestamp}] {message}")
        scroll_bar = self.log_window.verticalScrollBar()
        if scroll_bar:
            scroll_bar.setValue(scroll_bar.maximum())

    @pyqtSlot(bool, str)
    def _handle_connection_changed(self, is_connected: bool, status_msg: str):
        """연결 상태를 UI에 표시"""

        self.btn_send.setEnabled(is_connected)
        
        if is_connected:
            self.btn_connect.setText("연결됨 (성공)")
            self.btn_connect.setEnabled(False)
            self.btn_send.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #4CAF50; color: white;")
        else:
            self.btn_connect.setText("연결")
            self.btn_connect.setEnabled(True)
            self.btn_send.setStyleSheet("color: darkred; font-weight: bold; font-size: 14px; background-color: #dddddd;")

    @pyqtSlot(dict)
    def _handle_sequence_data(self, sequence_data: dict):
        """시퀀스 데이터를 UI에 표시"""
        
        # print(f"뷰에서 받은 데이터:\n{sequence_data}")

        # 1. 상단 헤더 출력
        total_steps = len(sequence_data)
        self.log(f"✅ 데이터 수신 완료: 총 {total_steps}개의 스텝")
        self.log("=" * 50)

        # 2. 각 스텝별 데이터 포맷팅 및 출력
        for step_id, data in sequence_data.items():
            # 예: {'feed': 10.0, 'x_coord': 95.899 ...} 
            # 보기 좋게 문자열로 변환합니다.
            
            # 주요 좌표만 보고 싶다면 아래처럼 키를 지정해서 가져올 수도 있습니다.
            # 지금은 들어온 모든 데이터를 한 줄로 나열해 보겠습니다.
            info_parts = []
            for key, value in data.items():
                # 키 이름이 너무 길면 줄여서 표시 (선택사항)
                # 예: x_coord -> X, tool_rpm_rotation -> RPM1 등
                # 여기서는 그대로 출력합니다.
                info_parts.append(f"{key}:{value}")
            
            line_str = ", ".join(info_parts)
            self.log(f"[Step {step_id}] {line_str}")

        self.log("=" * 50)
        
        # 첫 번째 데이터를 입력창에 자동 세팅하기
        self._show_command_on_input_line(sequence_data)



    ################
    # --- 헬퍼 --- #
    ################
    def _show_command_on_input_line(self, sequence_data: dict):
        """시퀀스 데이터의 첫 번째 스텝을 좌표 입력창에 보이기"""
        # 딕셔너리의 첫 번째 키를 가져옴 (보통 '1')
        first_key = next(iter(sequence_data))
        first_data = sequence_data[first_key]

        # 데이터 키(file parser에서 만든 키)와 UI 입력창 키 매핑
        # 파서의 키: 'x_coord', 'y_coord', 'z_coord', 'w_angle', 'p_angle', 'r_angle', 'feed'
        # UI의 키: 'X', 'Y', 'Z', 'W', 'P', 'R', 'F'
        
        mapping = {
            'X': 'x_coord',
            'Y': 'y_coord',
            'Z': 'z_coord',
            'W': 'w_angle',
            'P': 'p_angle',
            'R': 'r_angle',
            'F': 'feed'
        }

        try:
            for ui_key, data_key in mapping.items():
                if data_key in first_data:
                    value = str(first_data[data_key])
                    self.inputs[ui_key].setText(value)
            
            self.log(f"ℹ️ [Step {first_key}] 데이터를 입력창에 적용했습니다.")
            self.btn_send.setEnabled(True) # 전송 버튼 활성화
            
        except Exception as e:
            self.log(f"⚠️ 입력창 자동 채우기 실패: {e}")



    #########################
    # --- 이벤트 핸들러 --- #
    #########################
    def closeEvent(self, event): # type: ignore
        """
        창이 닫히려고 하면 PyQt 프레임워크가 자동으로 호출
        QWidget.closeEvent 오버라이딩
        """
        # plc 연결 끊기
        self.vm.disconnect_plc()

        # 종료 승인
        event.accept()