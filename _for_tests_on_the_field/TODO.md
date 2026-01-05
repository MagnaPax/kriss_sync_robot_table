## 툴 제어 위젯
- 공전 rpm
- 자전 rpm

## 턴테이블 제어 위젯
- rpm
- 각도

# FANUC
- World Coordinates
    - 절대위치
    - 현재위치
- User Coordinates
    - 절대위치
    - 현재위치

# 턴테이블
- 현재각도
- 현재 rpm


# World coordinates : 바닥(Base)을 기준으로 TCP:Tool Center Point 가 떨어진 만큼의 거리?
# User coordinates : 현재 위치
    - Set Origin : 초기화
# Target Position : Use Position 을 기준으로 이동하고 싶은 만큼의 거리
# 시퀀스의 값들 : User coordinates 기준 이동거리

---

# 만들어야 될 것들 (급한것+우선순위)

## IntegratedExecutor 에 시퀀스를 동시에 움직이는 로직 완성 <- 로봇팀이 만들어 줘야 된다

## User Coordinates 표시 위젯
- Set Origin(Target Position 초기화) 한 다음에 Load
- Set Origin 안 하고 Load 로 불러오면?
- 움직이지 않을때는 0값이 나타나는 것 같은데

## TaskManager
- 시퀀스 끝나면 Runtime 정지
- 시퀀스 진행 중에는 START 버튼 비활성화

## WorldCoordinatesWidget
- 구분선 표시
- 공전, 자전 rpm 표시값이 입력값의 * 6 으로 나오는 문제
- 턴테이블 속도값이 마이너스로 표시됨

## TargetPositionWidget
- GO TO 누르면 Use Position 에 나온 값을 기준으로 이동
    - 만약 User Position 이 100인데 타겟포지션도 100이면 움직이지 않는다

## WaypointsWidget
    - 현재 진행 시퀀스 한가운데에 고정
    - 진행전, 진행중, 진행끝 표시

## LogoWidget
## TurntableWidget

## FANUC + 턴테이블 공용 feed rate 입력 창
## TwinCAT 연결이 끊기면 화면 비활성화
## MacroSettingsDialog 매크로 값들 - World coordinates 값


## config/settings.ini 의 [App] 부분이 적용이 안 되고 있는것 같다

## 배포할때는 dll을 설치한 곳에서 찾아야 되지 않나
## 비상정지 버튼
## 최종 스타일 입힐때는 노트북(다크모드 아님)에 띄워서 모양 확인
## PC -- TwinCAT -- 가젯들 중 TwinCAT <-> 가젯들 연결은 어떻게 확인?
## 연결 끊기는 테스트 해야 됨
## 로그 메세지 전체 리팩토링
- core/exception_handler.py 와 core/exceptions.py 를 사용하도록 전체 교체
- WARNING 과 ERROR 정확히 구분
---



로봇이 움직이고 있는 도중에 계속 피드백을 물어보면 동작에 문제 안 생기나?
    로봇을 움직일 때 (Write): _UI1 (User Input) 영역에 씁니다.
    위치를 물어볼 때 (Read): _UO1 (User Output) 영역을 읽습니다.
        로봇은 움직이면서 자신의 위치를 여기에 써놓는다.
        앱은 로봇에게 직접 묻는게 아니라 이 값을 읽어올 뿐(계기판 자주본다고 운전 못하는게 아님)
    만약 클럭을 10ms처럼 극단적으로 빨리 하고 싶으면 비트들을 한꺼번에 읽어서 오는 방식(sum read)로 변경
---
