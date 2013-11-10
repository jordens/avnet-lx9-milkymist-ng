#ifndef __HW_MEM_H
#define __HW_MEM_H

#define FLASH_OFFSET_BITSTREAM	0x00000000 /* 384k */
#define FLASH_OFFSET_BIOS		0x00060000 /* 128k */
#define FLASH_OFFSET_APP		0x00080000 /* remaining space */

#define SDRAM_BASE			0x40000000

#define MINIMAC_RX0_BASE	0xb0000000
#define MINIMAC_RX1_BASE	0xb0000800
#define MINIMAC_TX_BASE		0xb0001000

#endif /* __HW_MEM_H */
