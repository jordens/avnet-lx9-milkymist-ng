#include <stdio.h>
#include <stdlib.h>
#include <console.h>
#include <string.h>
#include <system.h>
#include <irq.h>

#include <hw/csr.h>
#include <hw/mem.h>
#include <hw/common.h>

#include "tdcdtc.h"


void tr(void) {
	while (tdcdtc_ev_status_read() & TDCDTC_EV_TDC_READABLE) {
		printf("tdc: t=0x%08x c=0x%08x\n", tdcdtc_tdc_time_read(), tdcdtc_tdc_data_read());
		tdcdtc_tdc_next_write(1);
	}
}

void tw(char* time, char* chan, char* count) {
	char *c;
	unsigned int time2, chan2, count2, i;
	if ((*time == 0) || (*chan == 0)) {
		printf("tw <time> <chan> [count]\n");
		return;
	}
	time2 = strtoul(time, &c, 0);
	if(*c != 0) {
		printf("incorrect time\n");
		return;
	}
	chan2 = strtoul(chan, &c, 0);
	if(*c != 0) {
		printf("incorrect chan\n");
		return;
	}
	if(*count == 0) {
		count2 = 1;
	} else {
		count2 = strtoul(count, &c, 0);
		if(*c != 0) {
			printf("incorrect count\n");
			return;
		}
	}
	for (i=0; i<count2; i++) {
		if (!(tdcdtc_ev_status_read() & TDCDTC_EV_DTC_WRITABLE)) {
			printf("out fifo overrun\n");
			break;
		}
		tdcdtc_dtc_time_write(time2);
		tdcdtc_dtc_data_write(chan2);
		tdcdtc_dtc_next_write(1);
	}
}

void to(char* chan) {
	char *c;
	unsigned int chan2;
	if(*chan == 0) {
		chan2 = 0;
	} else {
		chan2 = strtoul(chan, &c, 0);
		if(*c != 0) {
			printf("incorrect chans\n");
			return;
		}
	}
	tdcdtc_out_en_write(chan2);
}

void tu(char* chan) {
	char *c;
	unsigned int chan2;
	if(*chan == 0) {
		chan2 = 0;
	} else {
		chan2 = strtoul(chan, &c, 0);
		if(*c != 0) {
			printf("incorrect chans\n");
			return;
		}
	}
	tdcdtc_up_en_write(chan2);
}

void td(char* chan) {
	char *c;
	unsigned int chan2;
	if(*chan == 0) {
		chan2 = 0;
	} else {
		chan2 = strtoul(chan, &c, 0);
		if(*c != 0) {
			printf("incorrect chans\n");
			return;
		}
	}
	tdcdtc_down_en_write(chan2);
}

void ts(void) {
	tdcdtc_flush_dtc_write(0);
	tdcdtc_flush_tdc_write(0);
	tdcdtc_arm_write(1);
	tdcdtc_force_write(1);
}

void tf(void) {
	tdcdtc_force_write(0);
	tdcdtc_arm_write(0);
	tdcdtc_flush_dtc_write(1);
	tdcdtc_flush_tdc_write(1);
}

void tc(void) {
	tdcdtc_zero_write(1);
}

void tp(void) {
	unsigned int status = tdcdtc_ev_status_read();

	printf("status:    0x%08x\n", status);
	printf("dtc: %d, dtc_under: %d, tdc: %d, tdc_over: %d, run: %d, wrap: %d\n",
			status & TDCDTC_EV_DTC_WRITABLE,
			status & TDCDTC_EV_DTC_UNDERFLOW,
			status & TDCDTC_EV_TDC_READABLE,
			status & TDCDTC_EV_TDC_OVERFLOW,
			status & TDCDTC_EV_STOPPED,
			status & TDCDTC_EV_WRAP);
	printf("arm %d, force: %d, flush_tdc: %d, flush_dtc: %d\n",
			tdcdtc_arm_read(),
			tdcdtc_force_read(),
			tdcdtc_flush_tdc_read(),
			tdcdtc_flush_dtc_read());
	printf("cycle:     0x%08x\n", tdcdtc_cycle_read());
	printf("out:       0x%08x\n", tdcdtc_out_en_read());
	printf("up:        0x%08x\n", tdcdtc_up_en_read());
	printf("down:      0x%08x\n", tdcdtc_down_en_read());
	printf("level:     0x%08x\n", tdcdtc_level_read());
}

void tl(char* wbone) {
	char *c;
	unsigned int wbone2;

	if(*wbone == 0) {
		wbone2 = 0;
	} else {
		wbone2 = strtoul(wbone, &c, 0);
		if(*c != 0) {
			printf("incorrect flag\n");
			return;
		}
	}

#define BUF_START 1024
#define MAX_IN_WAIT 0x100*BUF_START
	int buf = BUF_START;
	int dbuf = buf/2;
#define N_ITER 4096
	int t, dt, i, j, lat = 0;

	tf();
	tdcdtc_out_en_write(1);
	tdcdtc_up_en_write(1);
	tdcdtc_down_en_write(0);

	while (dbuf > 0) {
		dt = 0;
		for (i=0; i<N_ITER; i++) {
			tdcdtc_zero_write(1);
			tdcdtc_flush_dtc_write(0);
			tdcdtc_flush_tdc_write(0);
			tdcdtc_dtc_data_write(0);
			tdcdtc_dtc_time_write(0);
			tdcdtc_dtc_next_write(1);
			tdcdtc_dtc_data_write(1);
			tdcdtc_dtc_time_write(0x1000);
			tdcdtc_dtc_next_write(1);
			tdcdtc_dtc_data_write(0);
			tdcdtc_dtc_time_write(0x1008);
			tdcdtc_dtc_next_write(1);
			tdcdtc_dtc_data_write(1);

			tdcdtc_force_write(1);
			irq_setie(0);
			if (wbone2) {
				while ((tdcdtc_ev_status_read() & TDCDTC_EV_TDC_READABLE) == 0);
				t = MMPTR(TDCDTC_IN_TIME);
				MMPTR(TDCDTC_OUT_TIME) = t + buf;
				MMPTR(TDCDTC_OUT_WE) = 1;
			} else {
				while ((tdcdtc_ev_status_read() & TDCDTC_EV_TDC_READABLE) == 0);
				t = tdcdtc_tdc_time_read();
				tdcdtc_dtc_time_write(t + buf);
				tdcdtc_dtc_next_write(1);
			}
			irq_setie(1);

			tdcdtc_tdc_next_write(1);
			for (j=0; j<MAX_IN_WAIT; j++)
				if (tdcdtc_ev_status_read() & TDCDTC_EV_TDC_READABLE)
					break;
			dt += tdcdtc_tdc_time_read() - t;
			tdcdtc_tdc_next_write(1);
			tf();
			if (j == MAX_IN_WAIT)
				break;
		}
		printf("buf %d dbuf %d i %d j %d dt %d\n", buf, dbuf, i, j, dt);
		if (i == N_ITER) {
			lat = dt/N_ITER;
			buf -= dbuf;
		} else {
			buf += dbuf;
		}
		dbuf /= 2;
	}
	printf("final safe time buffer: %d latency: %d\n", buf, lat);
}


