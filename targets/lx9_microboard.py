import os
from fractions import Fraction

from migen.fhdl.std import *
from mibuild.generic_platform import ConstraintError

from misoclib import (lasmicon, lx9crg, spiflash, s6ddrphy, minimac3,
		gpio, tdcdtc)
from misoclib.gensoc import SDRAMSoC

class _LX9ClockPads:
	def __init__(self, platform):
		self.clk_y3 = platform.request("clk_y3")
		self.trigger_reset = 0
		try:
			self.trigger_reset = platform.request("user_btn", 0)
		except ConstraintError:
			pass
		ddram_clock = platform.request("ddram_clock")
		self.ddr_clk_p = ddram_clock.p
		self.ddr_clk_n = ddram_clock.n
		eth_clocks = platform.request("eth_clocks")
		# self.eth_phy_clk = eth_clocks.phy
		self.eth_rx_clk = eth_clocks.rx
		self.eth_tx_clk = eth_clocks.tx

class MiniSoC(SDRAMSoC):
	csr_map = {
		"minimac":				10,
	}
	csr_map.update(SDRAMSoC.csr_map)

	interrupt_map = {
		"minimac":		2,
	}
	interrupt_map.update(SDRAMSoC.interrupt_map)

	def __init__(self, platform, with_memtest=False):
		SDRAMSoC.__init__(self, platform,
			clk_freq=(75)*1000000,
			cpu_reset_address=0x00060000,
			sram_size=4096,
			l2_size=8192,
			with_memtest=with_memtest)

		sdram_geom = lasmicon.GeomSettings(
			bank_a=2,
			row_a=13,
			col_a=10
		)
		sdram_timing = lasmicon.TimingSettings(
			tRP=self.ns(15),
			tRCD=self.ns(15),
			tWR=self.ns(15),
			tWTR=2,
			tREFI=self.ns(7800, False),
			tRFC=self.ns(72),

			req_queue_size=8,
			read_time=32,
			write_time=16
		)
		self.submodules.ddrphy = s6ddrphy.S6DDRPHY(platform.request("ddram"),
				memtype="LPDDR", nphases=2, cl=3, rd_bitslip=1, wr_bitslip=3,
				dqs_ddr_alignment="C1")
		self.register_sdram_phy(self.ddrphy.dfi, self.ddrphy.phy_settings, sdram_geom, sdram_timing)

		# Wishbone
		self.submodules.spiflash = spiflash.SpiFlash(platform.request("spiflash"))
		self.submodules.minimac = minimac3.MiniMAC(platform.request("eth"))
		self.register_rom(self.spiflash.bus)
		self.add_wb_slave(lambda a: a[26:29] == 3, self.minimac.membus)

		# CSR
		self.submodules.crg = lx9crg.LX9CRG(_LX9ClockPads(platform), self.clk_freq)
		dip = Cat(*[platform.request("user_dip", i) for i in range(4)])
		led = Cat(*[platform.request("user_led", i) for i in range(4)])
		self.submodules.buttons = gpio.GPIOIn(dip)
		self.submodules.leds = gpio.GPIOOut(led)

		# Clock glue
		self.comb += [
			self.ddrphy.clk4x_wr_strb.eq(self.crg.clk4x_wr_strb),
			self.ddrphy.clk4x_rd_strb.eq(self.crg.clk4x_rd_strb)
		]
		platform.add_platform_command("""
PIN "BUFG_1.O" CLOCK_DEDICATED_ROUTE = FALSE;

NET "{clk100}" TNM_NET = "GRPclk100";
TIMESPEC "TSclk100" = PERIOD "GRPclk100" 10 ns HIGH 50%;
""", clk100=platform.lookup_request("clk_y3"))

		# add Verilog sources
		for d in ["mxcrg", "minimac3"]:
			platform.add_source_dir(os.path.join("verilog", d))

class LX9TDCDTC(MiniSoC):
	csr_map = {
		"tdcdtc":				17,
	}
	csr_map.update(MiniSoC.csr_map)

	interrupt_map = {
		"tdcdtc":				5,
	}
	interrupt_map.update(MiniSoC.interrupt_map)

	def __init__(self, platform, with_memtest=False):
		MiniSoC.__init__(self, platform, with_memtest)
		self.submodules.tdcdtc = tdcdtc.TdcDtcHostif(
				platform.request("pmod_diff"), hires=True)
		self.add_wb_slave(lambda a: a[25:29] == 7, self.tdcdtc.bus)
		self.comb += [
			self.tdcdtc.serdes_strb.eq(self.crg.tdcdtc_strb),
			]

def get_default_subtarget(platform):
	if platform.name == "lx9":
		return MiniSoC
	elif platform.name == "lx9tdcdtc":
		return LX9TDCDTC
