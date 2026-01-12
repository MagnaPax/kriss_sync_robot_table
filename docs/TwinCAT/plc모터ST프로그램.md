# 서보 모터

## ST 프로그램

### 선언부

#### 전역(GVL) 변수
- 축 3개 사용
```
{attribute 'qualified_only'}
VAR_GLOBAL
	Axis1: AXIS_REF;
	Axis2: AXIS_REF;
	Axis3: AXIS_REF;
	direction: MC_Direction;
END_VAR
```

### 사용부 (main)
```
mc_power1(
	Axis:= GVL.Axis1,
	Enable:= bServoOn1,
	Enable_Positive:= TRUE,
	Enable_Negative:= TRUE,
	Override:= 100.0,
	BufferMode:= ,
	Options:= ,
	Status=> ,
	Busy=> ,
	Error=> bError1,
	ErrorID=> nErrorID1);
	
mc_power2(
	Axis:= GVL.Axis2,
	Enable:= bServoOn2,
	Enable_Positive:= TRUE,
	Enable_Negative:= TRUE,
	Override:= 100.0,
	BufferMode:= ,
	Options:= ,
	Status=> ,
	Busy=> ,
	Error=> bError2,
	ErrorID=> nErrorID2);
	
mc_power3(
	Axis:= GVL.Axis3,
	Enable:= bServoOn3,
	Enable_Positive:= TRUE,
	Enable_Negative:= TRUE,
	Override:= 100.0,
	BufferMode:= ,
	Options:= ,
	Status=> ,
	Busy=> ,
	Error=> bError3,
	ErrorID=> nErrorID3);
	
mc_moveabs3(
	Axis:= GVL.Axis3,
	Execute:= bMoveAbs3,
	Position:= pos3,
	Velocity:= vel3,
	Acceleration:= ,
	Deceleration:= ,
	Jerk:= ,
	BufferMode:= ,
	Options:= ,
	Done=> bDone3,
	Busy=> bBusy3,
	Active=> ,
	CommandAborted=> ,
	Error=> ,
	ErrorID=> );
	
mc_vel1(
	Axis:= GVL.Axis1,
	Execute:= bMoveVel1,
	Velocity:= vel1,
	Acceleration:= ,
	Deceleration:= ,
	Jerk:= ,
	Direction:= GVL.direction,
	BufferMode:= ,
	Options:= ,
	InVelocity=> ,
	Busy=> bBusy1,
	Active=> ,
	CommandAborted=> ,
	Error=> ,
	ErrorID=> );
	
mc_vel2(
	Axis:= GVL.Axis2,
	Execute:= bMoveVel2,
	Velocity:= vel2,
	Acceleration:= ,
	Deceleration:= ,
	Jerk:= ,
	Direction:= ,
	BufferMode:= ,
	Options:= ,
	InVelocity=> ,
	Busy=> bBusy2,
	Active=> ,
	CommandAborted=> ,
	Error=> ,
	ErrorID=> );
	
mc_readpos1(
	Axis:= GVL.Axis1,
	Enable:= bReadPos1,
	Valid=> ,
	Busy=> ,
	Error=> ,
	ErrorID=> ,
	Position=> Act_pos1);
	
mc_readpos2(
	Axis:= GVL.Axis2,
	Enable:= bReadPos2,
	Valid=> ,
	Busy=> ,
	Error=> ,
	ErrorID=> ,
	Position=> Act_pos2);
	
mc_readpos3(
	Axis:= GVL.Axis3,
	Enable:= bReadPos3,
	Valid=> ,
	Busy=> ,
	Error=> ,
	ErrorID=> ,
	Position=> Act_pos3);
mc_readvel1(
	Axis:= GVL.Axis1,
	Enable:= bReadVel1,
	Valid=> ,
	Busy=> ,
	Error=> ,
	ErrorID=> ,
	ActualVelocity=> Act_vel1);	
	
mc_readvel2(
	Axis:= GVL.Axis2,
	Enable:= bReadVel2,
	Valid=> ,
	Busy=> ,
	Error=> ,
	ErrorID=> ,
	ActualVelocity=> Act_vel2);	
	
mc_readvel3(
	Axis:= GVL.Axis3,
	Enable:= bReadVel3,
	Valid=> ,
	Busy=> ,
	Error=> ,
	ErrorID=> ,
	ActualVelocity=> Act_vel3);	
	
mc_stop1(
	Axis:= GVL.Axis1,
	Execute:= bStop1,
	Deceleration:= ,
	Jerk:= ,
	Options:= ,
	Done=> ,
	Busy=> ,
	Active=> ,
	CommandAborted=> ,
	Error=> ,
	ErrorID=> );
	
mc_stop2(
	Axis:= GVL.Axis2,
	Execute:= bStop2,
	Deceleration:= ,
	Jerk:= ,
	Options:= ,
	Done=> ,
	Busy=> ,
	Active=> ,
	CommandAborted=> ,
	Error=> ,
	ErrorID=> );
	
mc_stop3(
	Axis:= GVL.Axis3,
	Execute:= bStop3,
	Deceleration:= ,
	Jerk:= ,
	Options:= ,
	Done=> ,
	Busy=> ,
	Active=> ,
	CommandAborted=> ,
	Error=> ,
	ErrorID=> );
	
mc_home1(
	Axis:= GVL.Axis1,
	Execute:= bHome1,
	Position:= 0.0,
	Velocity:= 600.0,
	Acceleration:= ,
	Deceleration:= ,
	Jerk:= ,
	BufferMode:= ,
	Options:= ,
	Done=> ,
	Busy=> bBusyHome1,
	Active=> ,
	CommandAborted=> ,
	Error=> ,
	ErrorID=> );
mc_home2(
	Axis:= GVL.Axis2,
	Execute:= bHome2,
	Position:= 0.0,
	Velocity:= 600.0,
	Acceleration:= ,
	Deceleration:= ,
	Jerk:= ,
	BufferMode:= ,
	Options:= ,
	Done=> ,
	Busy=> bBusyHome2,
	Active=> ,
	CommandAborted=> ,
	Error=> ,
	ErrorID=> );	
mc_home3(
	Axis:= GVL.Axis3,
	Execute:= bHome3,
	Position:= 0.0,
	Velocity:= 36.0,
	Acceleration:= ,
	Deceleration:= ,
	Jerk:= ,
	Direction:= MC_Positive_Direction,
	BufferMode:= ,
	Options:= ,
	Done=> ,
	Busy=> bBusyHome3,
	Active=> ,
	CommandAborted=> ,
	Error=> ,
	ErrorID=> );
	
mc_reset1(
	Axis:= GVL.Axis1,
	Execute:= bReset1,
	Done=> ,
	Busy=> ,
	Error=> ,
	ErrorID=> );
	
mc_reset2(
	Axis:= GVL.Axis2,
	Execute:= bReset2,
	Done=> ,
	Busy=> ,
	Error=> ,
	ErrorID=> );
	
mc_reset3(
	Axis:= GVL.Axis3,
	Execute:= bReset3,
	Done=> ,
	Busy=> ,
	Error=> ,
	ErrorID=> );
	
mc_setpos3(
	Axis:= GVL.Axis3,
	Execute:= bSetPos3,
	Position:= 0.0,
	Mode:= ,
	Options:= ,
	Done=> bSetDone3,
	Busy=> ,
	Error=> ,
	ErrorID=> );
	
IF Robot1._UO1.DO45 THEN
    CALDoneFlag := TRUE; (* 이 변수가 TRUE가 되는지 확인 *)
END_IF
IF bSetDone3 THEN
    bSetDoneFlag := TRUE; (* 이 변수가 TRUE가 되는지 확인 *)
END_IF
IF bSetDone3 THEN
    bSetDoneFlag := TRUE; (* 이 변수가 TRUE가 되는지 확인 *)
END_IF
IF Robot1._UI1.DI44= TRUE THEN
	bMoveAbs3:= TRUE;
END_IF
FEdge3_Move(CLK:= bBusy3);
IF FEdge3_Move.Q THEN
	bMoveAbs3:= FALSE;
END_IF
FEdge1_Home(CLK:= bBusyHome1);
IF FEdge1_Home.Q THEN
	bHome1:= FALSE;
END_IF
FEdge2_Home(CLK:= bBusyHome2);
IF FEdge2_Home.Q THEN
	bHome2:= FALSE;
END_IF
FEdge3_Home(CLK:= bBusyHome3);
IF FEdge3_Home.Q THEN
	bHome3:= FALSE;
	bSetPos3:= TRUE;
END_IF
REdge3_Setpos(CLK:= bSetDone3);
IF REdge3_Setpos.Q THEN
	bSetPos3:= FALSE;
END_IF
```