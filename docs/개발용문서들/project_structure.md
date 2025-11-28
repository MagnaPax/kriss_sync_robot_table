# KRISS Robot Sync 프로젝트 구조

## 최상위 구조

```
KRISS_ROBOT_SYNC/
├── .vscode/               # VSCode 편집기 설정
├── config/                # 애플리케이션 설정
├── core/                  # 앱의 핵심 엔진 및 기반 클래스
├── docs/                  # 프로젝트 문서
├── logs/                  # 로그 파일 저장 위치 (자동 생성)
├── models/                # 데이터 모델 및 순수 비즈니스 로직
├── resources/             # 아이콘, 이미지 등 정적 리소스
├── services/              # 파일 I/O, 외부 API 통신 등 서비스 로직
├── styles/                # QSS 스타일시트
├── tests/                 # 자동화된 테스트 코드 (pytest)
├── ui/                    # 사용자 인터페이스 (View)
├── utils/                 # 유틸리티 함수 및 클래스
├── view_models/           # 뷰-모델 (프레젠테이션 로직)
├── .gitignore             # Git 버전 관리에서 제외할 파일 목록
├── main.py                # 애플리케이션 메인 실행 파일
├── README.md              # 프로젝트 개요 및 사용법
└── requirements.txt       # Python 패키지 의존성 목록
```

## 📂 상세 구조

### `config` - 설정
애플리케이션의 경로, 설정 값 등 변경 가능한 값들을 관리
```
config/
├── __init__.py
└── paths.py             # 파일 및 디렉토리 경로 상수
```

### `core` - 핵심 엔진
애플리케이션의 생명주기, 전역 이벤트, 예외 처리 등 프로젝트의 기반을 이루는 핵심 로직을 포함
```
core/
├── __init__.py
├── application.py         # QApplication을 래핑하는 AppEngine (앱 생명주기 관리)
├── event_bus.py           # 전역 Publish/Subscribe 이벤트 버스 (싱글톤)
├── exception_handler.py   # 처리되지 않은 예외를 로깅하는 전역 훅
└── log_listener.py        # EventBus의 로그 이벤트를 구독하여 실제 로깅을 수행
```

### `docs` - 문서
프로젝트 관련 설계, 구조, 사용법 등 모든 문서를 관리
```
docs/
└── project_structure.md   # 현재 파일
```

### `models` - 데이터 모델
UI나 프레임워크에 의존하지 않는 순수한 데이터 구조와 비즈니스 로직을 정의
```
models/
├── __init__.py
├── position_model.py      # 좌표(Position) 데이터 클래스 및 관련 로직
└── sequence_model.py      # 시퀀스(Sequence) 데이터 클래스 및 실행 로직
```

### `resources` - 정적 리소스
애플리케이션에서 사용하는 아이콘, 이미지, 폰트 등을 저장
```
resources/
└── icons/
    └── kriss.gif          # KRISS 로고 아이콘
```

### `services` - 서비스
파일 시스템, 데이터베이스, 네트워크 API 등 외부 시스템과의 통신 및 데이터 처리를 담당
```
services/
├── __init__.py
└── macro_service.py       # 매크로 JSON 파일의 읽기/쓰기를 담당
```

### `styles` - 스타일시트
애플리케이션의 UI 스타일을 정의하는 QSS 파일을 관리
```
styles/
└── stylesheet.qss         # 전역 스타일시트
```

### `tests` - 테스트
`pytest`를 사용하여 각 모듈의 기능을 검증하는 자동화된 테스트 코드를 작성
```
tests/
├── __init__.py
├── conftest.py            # pytest 공통 fixture 및 설정
├── pytest.ini             # pytest 실행 설정
├── test_macro_service.py
├── test_macro_settings_dialog.py
└── test_sequence_model.py
```

### `ui` - 사용자 인터페이스 (View)
사용자가 직접 보고 상호작용하는 모든 UI 컴포넌트를 포함
```
ui/
├── __init__.py
├── main_window.py         # 애플리케이션의 메인 윈도우
├── dialogs/
│   ├── __init__.py
│   └── macro_settings_dialog.py # 매크로 설정 다이얼로그
└── widgets/
    ├── __init__.py
    ├── base_widget.py     # 모든 커스텀 위젯의 기반이 되는 추상 클래스
    └── target_position_widget.py # 타겟 위치 지정 및 매크로 관리 위젯
```

### `utils` - 유틸리티
로깅, 파일 처리, 환경 변수 관리 등 프로젝트 전반에서 재사용되는 보조 기능들을 모아놓는다
```
utils/
├── __init__.py
├── env.py                 # 개발/배포 환경 감지
├── file_exceptions.py     # 파일 처리 관련 커스텀 예외
├── file_handler.py        # JSON, CSV 등 파일 읽기/쓰기 함수
└── logger.py              # 전역 로깅 시스템
```

### `view_models` - 뷰-모델
View와 Model 사이를 중재하며, UI의 상태와 동작(프레젠테이션 로직)을 관리
```
view_models/
├── __init__.py
├── main_viewmodel.py      # MainWindow의 상태와 로직 관리 (예상)
├── macro_settings_dialog_viewmodel.py # 매크로 설정 다이얼로그의 로직
├── target_position_viewmodel.py       # TargetPositionWidget의 로직
└── target_position_viewmodel_worker.py # ViewModel의 비동기 작업을 처리하는 Worker
```
