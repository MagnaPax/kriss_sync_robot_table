# 비상 정지 (EMERGENCY STOP) 플로우 차트

이 문서는 '비상 정지' 버튼 클릭 시 발생하는 이벤트 흐름을 설명합니다.

## 🚨 설계 핵심: EventBus를 통한 전역 방송

비상 정지는 특정 모듈 하나가 아닌, 시스템의 여러 부분이 동시에 알아야 하는 매우 중요한 **전역 이벤트**입니다. 따라서 중앙 방송국 역할을 하는 `EventBus`를 통해 "비상 정지 발령!"이라는 신호를 모든 모듈에 한 번에 전파(Publish)하는 것이 가장 효율적이고 안전한 방식입니다.

각 모듈은 이 방송을 듣고(Subscribe), 각자 맡은 역할에 따라 비상 정지 절차를 수행합니다.

## 🔄 로직 흐름 (Flowchart)

```mermaid
graph TD
    %% ID와 라벨 분리
    subgraph UI_Layer ["UI Layer"]
        A[User clicks 'EMERGENCY STOP' Button]
    end

    subgraph Core_Layer ["Core Layer"]
        B(EventBus)
    end

    subgraph Listeners ["Listeners (Subscribers)"]
        C[PLC Controller Service]
        D[Sequence Executor ViewModel]
        E[UI State Manager]
        F[Logging Service]
    end

    A -- "emergency_stop_requested.emit()" --> B

    B -- "비상 정지 신호 수신" --> C
    B -- "비상 정지 신호 수신" --> D
    B -- "비상 정지 신호 수신" --> E
    B -- "비상 정지 신호 수신" --> F

    %% 수정된 부분: 텍스트를 모두 " " (큰따옴표)로 감쌌습니다.
    C --> C_Action{"모든 로봇 동작 즉시 중단<br/>(RSR 신호 OFF)"}
    D --> D_Action{"현재 실행 중인 시퀀스 중단<br/>(State: ERROR)"}
    E --> E_Action{"모든 버튼 비활성화,<br/>화면을 '비상 정지' 상태로 변경"}
    F --> F_Action{"'비상 정지 발생' 로그 기록"}
```

