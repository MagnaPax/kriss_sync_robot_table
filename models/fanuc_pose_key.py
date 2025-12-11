# models/fanuc_pose_key,py.py
from enum import Enum

class FANUCPoseKey(str, Enum):
    """
    FANUCPose (좌표 데이터 모델)의 구성요소 이름 정의

        목적:
            오타 방지 / 축 이름 관리

        역할:
            상수(Enum)

        동작:
            상태 없음(stateless)


        FANUCPose 와의 차이점 비유로 설명
                - Enum: 메뉴 이름
                    햄버거, 콜라, 감자튀김 <- 이런 목록 이름

                - FANUCPose: 실제 주문 내용
                    햄버거 2개, 콜라 1개, 감자튀김 1개

        사용 예:
            from models.fanuc_pose_key import FANUCPoseKey

            send_coordinate(pose.x, FANUCPoseKey.X)
            send_coordinate(pose.r, FANUCPoseKey.R)

            tag = FANUCPoseKey.P.ui_tag()
    """

    X = "X"
    Y = "Y"
    Z = "Z"
    W = "W"
    P = "P"
    R = "R"

    def fanuc_tag(self) -> str:
        return f"MAIN.Robot1._UI1.{self.value}_Check"
