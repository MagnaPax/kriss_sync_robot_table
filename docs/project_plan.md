```
kriss_sync_robot_turn_table/
│
├── main.py                          # 애플리케이션 진입점: QApplication 생성, MainWindow 인스턴스화, 이벤트 루프 실행. 예: from ui.main_window import MainWindow; app = QApplication([]); window = MainWindow(); window.show(); app.exec()
│
├── config/
│   ├── __init__.py                  # 패키지 초기화: 모듈 임포트 편의를 위한 빈 파일.
│   ├── settings.py                  # 전역 설정: 색상 팔레트(dict), 위젯 크기(tuple), 파일 경로(str) 등을 저장. 예: COLOR_PALETTE = {'primary': '#007BFF', 'error': '#DC3545'}; 구현: 클래스나 dict로 설정 로드/저장 기능.
│   └── constants.py                 # 상수: ADS 포트(int, e.g., 851), AMS Net ID(str, e.g., '127.0.0.1.1.1'), 타임아웃 초(int, e.g., 5). 예: ADS_TIMEOUT = 5000; 읽기 전용으로 정의.
│
│
├── core/                            # 이 앱의 인프라 : 얘들은 UI도 데이터도 모른다. 오직 '앱이 어떻게 실행되는가'만 안다
│   ├── __init__.py                  # 패키지 초기화.
│   ├── application.py               # 앱의 부트스트랩(QApplication 래퍼)
│   └── event_bus.py                 # 전역 이벤트 : Observer 패턴 구현, pub/sub 메커니즘. 예: class EventBus(QObject): turntable_angle_changed = pyqtSignal(float); def emit_event(self, event, data): ...
│   └── exception_handler.py         # 전역 예외 훅
│   └── threads.py                   # 워커 스레드 풀
│
####################################################
# Model이 실행 → ViewModel이 상태 방송 → View가 표시
####################################################
│
├── models/                         # 이들은 UI, ViewModel, EventBus를 "전혀" 모른다. 오직 "데이터가 무엇인가"만 정의한다
│   ├── __init__.py                 # 패키지 초기화.
│   ├── macro_model.py              # 매크로 데이터 저장/읽기/검증
│   ├── robot_model.py              # 로봇 상태, 궤적 계산
│   ├── calibration_model.py        # 보정 데이터
│   ├── sequence_model.py           # 시퀀스 데이터, 실행 로직, 상태 저장
│   ├── vision_model.py             # 이미지 처리
│   └── safety_model.py             # 안전성 로직
│
├── view_models/                    # UI(View)의 요청을 받아 비즈니스 로직을 실행하는 "중간 관리자"
│   │                               # View의 상태(State)를 관리하고, Model의 데이터를 가공하여 View에 제공하는 역할.
│   │                               # 이들은 'Model'과 'EventBus', 'utils'를 알지만, 'ui' 폴더는 모른다
│   ├── __init__.py
│   ├── macro_view_model.py         # (파일 I/O, 예외 처리, 로그 발행, 데이터 가공)
│   ├── robot_view_model.py         # 
│   ├── calibration_view_model.py
│   ├── sequence_view_model.py      # 현재 인덱스, 진행률, UI 상태 방출 - 뷰가 구독하는 신호
│   ├── vision_view_model.py
│   └── safety_view_model.py
│
│
├── communication/
│   ├── __init__.py                  # 패키지 초기화.
│   ├── twincat_client.py            # TwinCAT ADS 통신: pyads 라이브러리 래핑, connect/disconnect, read/write_variable 메서드. 예: class TwinCATClient: def connect(self, net_id, port): self.plc = pyads.Connection(net_id, port); 백그라운드 스레드(QThread)로 주기적 읽기.
│   ├── fanuc_client.py              # FANUC 로봇 통신 (옵션): 소켓이나 API 연동, 위치 데이터 읽기/쓰기. 예: class FanucClient: def get_position(self): ... (미구현 시 주석 처리).
│   └── data_model.py                # 데이터 모델: 상태 클래스 정의. 예: class RobotState(QObject): position_changed = pyqtSignal(dict); def __init__(self): self.x = 0.0; self.y = 0.0; ... (PyQt 시그널 포함).
│
├── ui/
│   ├── __init__.py                  # 패키지 초기화.
│   ├── main_window.py               # 메인 윈도우: QMainWindow 상속, 메뉴바/툴바/상태바 설정, 패널 배치. 예: class MainWindow(QMainWindow): def __init__(self): self.central_widget = QWidget(); self.setCentralWidget(self.central_widget); layout = QHBoxLayout(); layout.addWidget(LeftPanel())
│   │
│   ├── widgets/                     # 재사용 가능한 위젯들: 각 위젯은 BaseWidget 상속, update_data 메서드 구현.
│   │   ├── __init__.py              # 패키지 초기화: 모든 위젯 임포트.
│   │   ├── base_widget.py           # 공통 베이스 클래스: QWidget 상속, 공통 스타일/시그널 연결. 예: class BaseWidget(QWidget): def update_data(self, data): pass
│   │   ├── turntable_gauge.py       # TurnTable 원형 게이지: QPainter로 360도 게이지 그리기, set_angle 메서드. 예: def paintEvent(self, event): painter = QPainter(self); painter.drawArc(...); 애니메이션(QPropertyAnimation) 지원.
│   │   ├── robot_visualization.py   # Robot 시각화: QPainter로 로봇 팔/위치 그리기, set_position 메서드. 예: 2D 그리드 표시, resizeEvent로 크기 조정.
│   │   ├── batch_table.py           # Batch Processing 테이블: QTableWidget 상속, 행별 색상/프로그레스 바. 예: def update_row(self, index, state): self.setItem(index, 0, QTableWidgetItem(state))
│   │   ├── status_indicator.py      # 상태 표시 (점등): QColor로 녹/적/황 점등, 애니메이션. 예: class StatusIndicator(QWidget): def set_status(self, color): self.color = color; self.update()
│   │   ├── coordinate_input.py      # X,Y,Z,W,P,R 입력 위젯: QLineEdit 배열, validators.py와 연동. 예: self.x_input = QLineEdit(); self.x_input.setValidator(QDoubleValidator())
│   │   └── log_viewer.py            # 로그 표시 위젯: QTextEdit 상속, 스크롤/필터링. 예: def append_log(self, message): self.append(message); self.moveCursor(QTextCursor.End)
│   │
│   ├── panels/                      # 대형 패널들: 위젯 조합으로 구성, QGroupBox나 QWidget 상속.
│   │   ├── __init__.py              # 패키지 초기화.
│   │   ├── left_panel.py            # 왼쪽 패널: TurnTableGauge + Current State 위젯 포함. 예: layout = QVBoxLayout(); layout.addWidget(TurnTableGauge())
│   │   ├── center_panel.py          # 중앙 패널: RobotVisualization + Control 버튼. 예: self.connect_btn = QPushButton('Connect'); self.connect_btn.clicked.connect(self.on_connect)
│   │   └── right_panel.py           # 오른쪽 패널: BatchTable + LogViewer. 예: self.load_btn = QPushButton('Load Batch'); self.load_btn.clicked.connect(self.load_file)
│   │
│   └── dialogs/                     # 다이얼로그들: QDialog 상속, 모달/논모달 설정.
│       ├── __init__.py              # 패키지 초기화.
│       ├── settings_dialog.py       # 설정 창: QFormLayout으로 입력 필드, 저장 버튼. 예: self.net_id_input = QLineEdit(); self.save_btn.clicked.connect(self.save_settings)
│       ├── about_dialog.py          # 정보 창: QLabel로 버전/저작권 표시. 예: self.setWindowTitle('About'); self.label = QLabel('Version 1.0')
│       └── emergency_dialog.py      # 비상정지 확인 창: QMessageBox 상속, 확인/취소 버튼. 예: reply = QMessageBox.question(self, 'Emergency', 'Stop now?')
│
├── utils/
│   ├── __init__.py                  # 패키지 초기화.
│   ├── file_handler.py              # 파일 입출력: CSV/JSON 로드/저장, 배치 파일 파싱. 예: def load_csv(self, path): return pd.read_csv(path) (pandas 옵션).
│   ├── logger.py                    # 로깅 시스템: logging 모듈 래핑, 파일/콘솔/UI 출력. 예: logger = logging.getLogger(__name__); logger.info('Message')
│   └── validators.py                # 입력 검증: QValidator 상속 클래스들. 예: class CoordinateValidator(QDoubleValidator): def validate(self, input_text, pos): ...
│
├── styles/
│   ├── __init__.py                  # 패키지 초기화.
│   ├── theme.py                     # 테마 관리: 다크/라이트 모드 전환, QColor 정의. 예: def apply_theme(app, mode='dark'): app.setStyleSheet(stylesheet.qss if mode == 'dark' else '')
│   └── stylesheet.qss               # QSS 스타일시트: CSS-like 스타일. 예: QPushButton { background-color: #007BFF; color: white; } /* 버튼 스타일 */
│
├── resources/
│   ├── icons/                       # 아이콘 파일들: SVG/PNG 형식, 위젯에 사용.
│   │   ├── connect_icon.svg         # 연결 버튼 아이콘 예시.
│   │   ├── stop_icon.png            # 정지 버튼 아이콘 예시.
│   │   └── robot_icon.ico           # 앱 아이콘 예시.
│   └── images/                      # 이미지 파일들: 배경/그래픽 이미지.
│       ├── background.jpg           # 메인 윈도우 배경 예시.
│       └── robot_arm.png            # 로봇 시각화 이미지 예시.
│
├── tests/
│   ├── __init__.py                  # 패키지 초기화.
│   ├── test_widgets.py              # 위젯 단위 테스트: pytest로 update_data 등 테스트. 예: def test_turntable_gauge(): widget = TurnTableGauge(); assert widget.angle == 0
│   ├── test_communication.py        # 통신 모듈 테스트: mock PLC로 connect/read 테스트.
│   └── test_integration.py          # 통합 테스트: 전체 워크플로우 시뮬레이션.
│
├── docs/
│   ├── architecture.md              # 아키텍처 문서: MVC 패턴, 데이터 흐름 다이어그램 설명.
│   ├── api_reference.md             # API 레퍼런스: 각 클래스/메서드 문서화 (e.g., TwinCATClient.connect() 설명).
│   └── user_guide.md                # 사용자 가이드: UI 사용법, 스크린샷 포함.
│
├── requirements.txt                 # Python 패키지 의존성: PyQt6==6.5.0\npyads==3.3.0\npandas==2.0.0 등.
├── README.md                        # 프로젝트 개요: 설치 방법, 실행 명령, 기여 가이드.
└── .gitignore                       # 무시 파일: *.pyc, __pycache__/, *.exe 등.
```

#### **단계별 개발 순서 (Milestones, 재구성)**
위 확장된 구조를 바탕으로 이전 순서를 업데이트했습니다. Phase 0에서 이 구조 생성을 명시하고, 각 Phase에서 관련 파일 참조를 추가했습니다. UI 우선 원칙 유지.

1. **Phase 0: 프로젝트 초기화 (1-2일, 의존성: 없음)**
   - 작업: Git 초기화, 확장된 폴더 구조 생성(위 구조 따라 mkdir/ui/widgets 등), requirements.txt 작성(PyQt6, pyads 등), README.md 초안 작성.
   - 산출물: 프로젝트 스켈레톤, config/constants.py에 기본 상수 입력.
   - 이유: 기반 마련, 구조부터 자세히 정의.

2. **Phase 1: UI 프로토타이핑 및 정적 레이아웃 완성 (3-5일, 의존성: Phase 0)**
   - 작업: ui/main_window.py 기본 틀, ui/widgets/에 모든 위젯 클래스 생성(turntable_gauge.py 등 paintEvent 고정 값), ui/panels/에 패널 배치, styles/stylesheet.qss 작성 및 적용, resources/icons/에 샘플 아이콘 추가.
   - 산출물: 정적 목업 앱 (시안 동일, 클릭 무응답).
   - 이유: UI 우선으로 컨펌 용이, 위젯 모듈화 강조.

3. **Phase 2: UI 로직 분리 및 내부 데이터 시뮬레이션 (3-4일, 의존성: Phase 1)**
   - 작업: core/event_bus.py 구현(시그널 정의), communication/data_model.py에 상태 클래스, ui/widgets/에 update_data 슬롯 연결, QTimer 시뮬레이터 추가.
   - 산출물: 인터랙티브 프로토타입 (가짜 데이터로 동작).
   - 이유: UI-로직 분리, event_bus로 위젯 간 통신.

4. **Phase 3: ADS 통신 계층 연동 및 Core 시스템 구축 (4-5일, 의존성: Phase 2)**
   - 작업: communication/twincat_client.py 구현(connect/read/write, 스레드), fanuc_client.py 옵션 스켑, core/application.py로 앱 래퍼, 시뮬레이터 제거 후 실제 연결.
   - 산출물: 실시간 데이터 표시/제어 버전.
   - 이유: 통신 계층 분리, pyads 활용.

5. **Phase 4: 기능 완성 및 안정화 (4-5일, 의존성: Phase 3)**
   - 작업: utils/file_handler.py와 logger.py 구현(배치 로드/로그), ui/dialogs/에 다이얼로그 추가, styles/theme.py로 테마 전환, utils/validators.py 입력 검증, 예외 처리.
   - 산출물: 완성된 앱 (파일 I/O, 로그, 다이얼로그 포함).

6. **Phase 5: 테스트, 문서화 및 배포 (3-4일, 의존성: Phase 4)**
   - 작업: tests/에 pytest 스크립트 작성, docs/에 architecture.md 등 문서화, PyInstaller로 .exe 패키징.
   - 산출물: 테스트 리포트, 배포 패키지, user_guide.md.

#### **전체 일정 요약 및 의존성 표**
총 예상 기간: 18-25일 (약 4-5주, 확장으로 약간 증가).

| Phase | 기간 | 우선순위 | 의존성 | 주요 산출물 |
|-------|------|---------|--------|------------|
| 0 | 1-2일 | ⭐⭐⭐⭐⭐ | 없음 | 확장된 스켈레톤 |
| 1 | 3-5일 | ⭐⭐⭐⭐⭐ | 0 | 정적 UI |
| 2 | 3-4일 | ⭐⭐⭐⭐ | 1 | 동적 프로토타입 |
| 3 | 4-5일 | ⭐⭐⭐⭐⭐ | 2 | 통신 연동 |
| 4 | 4-5일 | ⭐⭐⭐⭐ | 3 | 기능 완성 |
| 5 | 3-4일 | ⭐⭐⭐ | 4 | 테스트/배포 |

#### **MVP 전략 (최소 실행 가능 제품)**
- 1단계 (Phase 0-2, 1-2주): UI 프로토타입 → 시연.
- 2단계 (Phase 3, 1주): 통신 연동 → 모니터링.
- 3단계 (Phase 4-5, 1-2주): 자동화/테스트 → 완성.

이 재구성된 순서는 확장된 구조를 반영하여 더 구체적이며, 개발 효율성을 높입니다. 실제 시 유연 조정하세요.













### 최종 결과: Feature 브랜치 네이밍 규칙 및 예시
아래는 `kriss_sync_robot_turn_table/` 프로젝트에 최적화된 feature 브랜치 네이밍 규칙입니다. 규칙은 명확성, 모듈화, 협업 효율성을 고려하며, 프로젝트의 Phase와 폴더 구조를 반영합니다.

#### **브랜치 네이밍 규칙**
1. **형식**: `유형/모듈-작업내용[-이슈번호]`
   - **유형**: 작업 종류를 나타냄. 예: `feat`(기능 추가), `fix`(버그 수정), `refactor`(리팩토링), `docs`(문서), `test`(테스트).
   - **모듈**: 프로젝트 폴더 구조 기반 (예: ui, widgets, communication, core 등).
   - **작업내용**: 동사를 포함한 구체적 설명 (예: implement-turntable-gauge, add-connect-button).
   - **이슈번호** (선택): 이슈 관리 시스템 사용 시 추가 (예: KRISS-45).
2. **명명 규칙**:
   - 소문자 사용, 단어 간 `-`로 연결 (camelCase 대신 kebab-case).
   - 동사로 시작해 작업 의도 명확히 (예: implement, add, update).
   - 50자 이내로 간결히, 모듈과 작업 내용으로 충분히 식별 가능해야 함.
3. **이유**: 프로젝트의 모듈화 구조(ui/widgets/, communication/ 등)를 반영하고, UI 우선 개발(g02.md)에 맞춰 위젯별 작업 명확화. 협업 시 PR과 Git 로그에서 작업 추적 용이.

#### **Phase별 추천 브랜치 이름 예시**
각 Phase의 주요 작업과 폴더 구조를 기반으로 브랜치 이름 예시를 제공합니다.

1. **Phase 0: 프로젝트 초기화**
   - `feat/project-init`: Git, 폴더 구조, requirements.txt 설정.
   - `docs/readme-setup`: README.md 초안 작성.
   - 예: `git checkout -b feat/project-init`

2. **Phase 1: UI 프로토타이핑 및 정적 레이아웃**
   - `feat/ui-main-window`: main_window.py 기본 틀 구현.
   - `feat/widgets-turntable-gauge`: turntable_gauge.py 정적 paintEvent.
   - `feat/widgets-robot-visualization`: robot_visualization.py 정적 그리기.
   - `feat/styles-qss`: stylesheet.qss 작성.
   - 예: `git checkout -b feat/widgets-turntable-gauge-KRISS-10`

3. **Phase 2: UI 로직 분리 및 시뮬레이션**
   - `feat/core-event-bus`: event_bus.py 구현.
   - `feat/core-data-model`: data_model.py 상태 클래스.
   - `feat/widgets-update-logic`: 위젯에 update_data 연결.
   - 예: `git checkout -b feat/core-event-bus`

4. **Phase 3: ADS 통신 계층 연동**
   - `feat/communication-twincat-client`: twincat_client.py 구현.
   - `feat/core-ads-integration`: ViewModel-ADS 연결.
   - 예: `git checkout -b feat/communication-twincat-client-KRISS-25`

5. **Phase 4: 기능 완성 및 안정화**
   - `feat/utils-file-handler`: file_handler.py 배치 파일 처리.
   - `feat/widgets-log-viewer`: log_viewer.py 로그 표시.
   - `feat/dialogs-settings`: settings_dialog.py 구현.
   - 예: `git checkout -b feat/utils-file-handler`

6. **Phase 5: 테스트, 문서화 및 배포**
   - `test/widgets-unit`: test_widgets.py 단위 테스트.
   - `docs/architecture`: architecture.md 작성.
   - `feat/build-package`: PyInstaller로 .exe 빌드.
   - 예: `git checkout -b test/widgets-unit`

#### **전체 일정 및 브랜치 요약 표**
| Phase | 기간 | 주요 브랜치 예시 | 의존성 | 산출물 |
|-------|------|------------------|--------|--------|
| 0 | 1-2일 | feat/project-init, docs/readme-setup | 없음 | 스켈레톤 |
| 1 | 3-5일 | feat/ui-main-window, feat/widgets-turntable-gauge | 0 | 정적 UI |
| 2 | 3-4일 | feat/core-event-bus, feat/widgets-update-logic | 1 | 동적 프로토타입 |
| 3 | 4-5일 | feat/communication-twincat-client, feat/core-ads-integration | 2 | 통신 연동 |
| 4 | 4-5일 | feat/utils-file-handler, feat/dialogs-settings | 3 | 기능 완성 |
| 5 | 3-4일 | test/widgets-unit, docs/architecture | 4 | 테스트/배포 |

#### **추가 팁**
- **이슈 연동**: JIRA/GitHub Issues 사용 시, 브랜치 끝에 `KRISS-번호` 추가 (예: feat/widgets-turntable-gauge-KRISS-10).
- **PR 규칙**: 브랜치 이름과 커밋 메시지가 작업 내용과 일치하도록. 예: 커밋 메시지 "Implement TurnTableGauge paintEvent for static rendering".
- **브랜치 관리**: 작업 완료 후 main/develop 브랜치에 병합, 오래된 브랜치는 삭제.

이 네이밍 규칙은 프로젝트의 모듈화와 UI 우선 원칙을 반영하며, 협업과 유지보수에 최적화되어 있습니다. 필요 시 이슈 관리 툴에 맞게 조정하세요.