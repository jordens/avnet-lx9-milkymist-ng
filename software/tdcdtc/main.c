#include <stdio.h>
#include <stdlib.h>
#include <console.h>
#include <string.h>
#include <uart.h>
#include <system.h>
#include <id.h>
#include <irq.h>
#include <crc.h>

#include <hw/csr.h>
#include <hw/mem.h>

#include "tdcdtc.h"


static char *get_token(char **str)
{
	char *c, *d;

	c = (char *)strchr(*str, ' ');
	if(c == NULL) {
		d = *str;
		*str = *str+strlen(*str);
		return d;
	}
	*c = 0;
	d = *str;
	*str = c+1;
	return d;
}

static void readstr(char *s, int size)
{
	char c[2];
	int ptr;

	c[1] = 0;
	ptr = 0;
	while(1) {
		c[0] = readchar();
		switch(c[0]) {
			case 0x7f:
			case 0x08:
				if(ptr > 0) {
					ptr--;
					putsnonl("\x08 \x08");
				}
				break;
			case 0x07:
				break;
			case '\r':
			case '\n':
				s[ptr] = 0x00;
				putsnonl("\n");
				return;
			default:
				putsnonl(c);
				s[ptr] = c[0];
				ptr++;
				break;
		}
	}
}

static void do_command(char *c)
{
	char *token;

	token = get_token(&c);

	if(strcmp(token, "tp") == 0) tp();
	else if(strcmp(token, "tr") == 0) tr();
	else if(strcmp(token, "tw") == 0) tw(get_token(&c), get_token(&c), get_token(&c));
	else if(strcmp(token, "to") == 0) to(get_token(&c));
	else if(strcmp(token, "tu") == 0) tu(get_token(&c));
	else if(strcmp(token, "td") == 0) td(get_token(&c));
	else if(strcmp(token, "ts") == 0) ts();
	else if(strcmp(token, "tf") == 0) tf();
	else if(strcmp(token, "tc") == 0) tc();
	else if(strcmp(token, "tl") == 0) tl(get_token(&c));

	else if(strcmp(token, "") != 0)
		printf("Command not found\n");
}

int main(void)
{
	char buffer[64];
	irq_setmask(0);
	irq_setie(1);
	uart_init();

	puts("TDCDTC "__DATE__" "__TIME__"\n");

	while(1) {
		putsnonl("\e[1mTDCDTC>\e[0m ");
		readstr(buffer, 64);
		do_command(buffer);
	}
	return 0;
}
