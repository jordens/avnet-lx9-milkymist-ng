#ifndef __HW_TDCDTC_H
#define __HW_TDCDTC_H

#define TDCDTC_MEM_BASE		0xb8000000
#define TDCDTC_CYCLE		(0x0*4+TDCDTC_MEM_BASE)
#define TDCDTC_IN_TIME		(0x10*4+TDCDTC_MEM_BASE)
#define TDCDTC_IN_DATAE		(0x11*4+TDCDTC_MEM_BASE)
#define TDCDTC_IN_RE		(0x12*4+TDCDTC_MEM_BASE)
#define TDCDTC_OUT_TIME		(0x20*4+TDCDTC_MEM_BASE)
#define TDCDTC_OUT_DATA		(0x21*4+TDCDTC_MEM_BASE)
#define TDCDTC_OUT_WE		(0x22*4+TDCDTC_MEM_BASE)

#define TDCDTC_EV_TDC_READABLE	0x01
#define TDCDTC_EV_DTC_WRITABLE	0x02
#define TDCDTC_EV_TDC_OVERFLOW	0x04
#define TDCDTC_EV_DTC_UNDERFLOW	0x08
#define TDCDTC_EV_STARTED		0x10
#define TDCDTC_EV_STOPPED		0x20
#define TDCDTC_EV_WRAP			0x40

void tr(void);
void tw(char* time, char* chan, char* count);
void to(char* chan);
void tu(char* chan);
void td(char* chan);
void tp(void);
void ts(void);
void tf(void);
void tc(void);
void tl(char* wbone);

#endif /* __HW_TDCDTC_H */
