#include <stdio.h>
#include <stdlib.h>

#include <irq.h>
#include <uart.h>
#include <console.h>

int main(void)
{
	irq_setmask(0);
	irq_setie(1);
	uart_init();
	
	puts("Hello world built "__DATE__" "__TIME__"\n");

	while(1) {
	}
	
	return 0;
}
