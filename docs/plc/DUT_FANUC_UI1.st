// FANUC UI1 구조체
TYPE DUT_FANUC_UI1 :
STRUCT
	// 25~42(UI)
	UI01_IMSP : BIT := 1;
	UI02_Hold : BIT := 1;
	UI03_SFSP : BIT := 1;
	UI04_CycleStop : BIT;
	UI05_FaultReset : BIT;
	UI06_Start : BIT;
	UI07_Home : BIT;
	UI08_Enable : BIT := 1;
	UI09_RSR1, UI10_RSR2, UI11_RSR3, UI12_RSR4, UI13_RSR5, UI14_RSR6, UI15_RSR7, UI16_RSR8 : BIT;
	UI17_PNSStrobe : BIT;
	UI18_ProdStart : BIT;
	
	// 43~44(Reserved)
	DI43, DI44 : BIT;
	
	// 45~48(Feed_High_Bit)
	Fh0, Fh1, Fh2, Fh3 : BIT;
	// 49~64(Feed_Low_Bit)
	Fl0, Fl1, Fl2, Fl3, Fl4, Fl5, Fl6, Fl7,
	Fl8, Fl9, Fl10, Fl11, Fl12, Fl13, Fl14, Fl15 : BIT;
	
	// 65~72(X_High_Bit)
	Xh0, Xh1, Xh2, Xh3, Xh4, Xh5, Xh6, Xh7 : BIT;
	// 73~88(X_Low_Bit)
	Xl0, Xl1, Xl2, Xl3, Xl4, Xl5, Xl6, Xl7,
	Xl8, Xl9, Xl10, Xl11, Xl12, Xl13, Xl14, Xl15 : BIT;
	// 107~114(Y_High_Bit)
	Yh0, Yh1, Yh2, Yh3, Yh4, Yh5, Yh6, Yh7 : BIT;
	// 115~130(Y_Low_Bit)
	Yl0, Yl1, Yl2, Yl3, Yl4, Yl5, Yl6, Yl7,
	Yl8, Yl9, Yl10, Yl11, Yl12, Yl13, Yl14, Yl15 : BIT;
	// 131~138(Z_Hihg_Bit)
	Zh0, Zh1, Zh2, Zh3, Zh4, Zh5, Zh6, Zh7 : BIT;
	// 139~154(Z_Low_Bit)
	Zl0, Zl1, Zl2, Zl3, Zl4, Zl5, Zl6, Zl7,
	Zl8, Zl9, Zl10, Zl11, Zl12, Zl13, Zl14, Zl15 : BIT;
	// 155~162(W_High_Bit)
	Wh0, Wh1, Wh2, Wh3, Wh4, Wh5, Wh6, Wh7 : BIT;
	// 163~178(W_Low_Bit)
	Wl0, Wl1, Wl2, Wl3, Wl4, Wl5, Wl6, Wl7,
	Wl8, Wl9, Wl10, Wl11, Wl12, Wl13, Wl14, Wl15 : BIT;
	// 179~186(P_High_Bit)
	Ph0, Ph1, Ph2, Ph3, Ph4, Ph5, Ph6, Ph7 : BIT;
	// 187~202(P_Low_Bit)
	Pl0, Pl1, Pl2, Pl3, Pl4, Pl5, Pl6, Pl7,
	Pl8, Pl9, Pl10, Pl11, Pl12, Pl13, Pl14, Pl15 : BIT;
	// 203~210(R_High_Bit)
	Rh0, Rh1, Rh2, Rh3, Rh4, Rh5, Rh6, Rh7 : BIT;
	// 211~226(R_Low_Bit)
	Rl0, Rl1, Rl2, Rl3, Rl4, Rl5, Rl6, Rl7,
	Rl8, Rl9, Rl10, Rl11, Rl12, Rl13, Rl14, Rl15 : BIT;
	
	// 227~232(Check)
	X_Check : BIT := 0;
	Y_Check : BIT := 0;
	Z_Check : BIT := 0;
	W_Check : BIT := 0;
	P_Check : BIT := 0;
	R_Check : BIT := 0;
	
	// 233, 234(Reserved)
	DI233, DI234 : BIT;
	
END_STRUCT
END_TYPE
