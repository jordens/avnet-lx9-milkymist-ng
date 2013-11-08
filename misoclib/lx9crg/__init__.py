from fractions import Fraction

from migen.fhdl.std import *

class LX9CRG(Module):
	def __init__(self, pads, outfreq1x):
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_sys_reset_less = ClockDomain(reset_less=True)
		self.clock_domains.cd_sdram_half = ClockDomain()
		self.clock_domains.cd_sdram_full_wr = ClockDomain()
		self.clock_domains.cd_sdram_full_rd = ClockDomain()
		self.clock_domains.cd_eth_rx = ClockDomain()
		self.clock_domains.cd_eth_tx = ClockDomain()
		self.clock_domains.cd_base = ClockDomain(reset_less=True)
		self.clock_domains.cd_tdcdtc = ClockDomain()

		self.clk4x_wr_strb = Signal()
		self.clk4x_rd_strb = Signal()
		self.tdcdtc_strb = Signal()

		###

		self.comb += self.cd_sys_reset_less.clk.eq(self.cd_sys.clk)

		rst_debounce = Signal(20)
		self.sync.sys_reset_less += [
				If(pads.trigger_reset,
					rst_debounce.eq(0xfffff),
				).Elif(rst_debounce != 0,
					rst_debounce.eq(rst_debounce - 1),
				),
				self.cd_sys.rst.eq(rst_debounce != 0),
			]

		#clkin, infreq = pads.clk_y1, 40*1000000//2
		p, q = 8, 4
		clkin, infreq = pads.clk_y3, Fraction(100*1000000, q)
		ratio = Fraction(outfreq1x)/infreq
		in_period = float(Fraction(1e9)/infreq)

		f_mult = ratio.numerator
		f_div = ratio.denominator
		vco = f_mult*p*infreq
		assert vco >= 400e6 and vco <= 1000e6, vco

		sdr_clkin = Signal()
		self.specials += Instance("IBUFG", i_I=clkin, o_O=sdr_clkin)

		clkdiv = Signal()
		self.specials += Instance("BUFIO2", p_DIVIDE=q,
			p_DIVIDE_BYPASS="FALSE", p_I_INVERT="FALSE",
			i_I=sdr_clkin, o_DIVCLK=clkdiv)

		pll_lckd = Signal()
		buf_pll_fb = Signal()
		pllout0 = Signal()
		pllout1 = Signal()
		pllout2 = Signal()
		pllout3 = Signal()
		pllout4 = Signal()
		pllout5 = Signal()

		self.specials.pll = Instance("PLL_ADV",
				p_BANDWIDTH="OPTIMIZED", p_COMPENSATION="INTERNAL", p_REF_JITTER=0.1,
				p_SIM_DEVICE="SPARTAN6",
				p_CLK_FEEDBACK="CLKFBOUT", p_DIVCLK_DIVIDE=1,
				p_CLKFBOUT_MULT=p*f_mult, p_CLKFBOUT_PHASE=0.,
				i_DADDR=0, i_DCLK=0, i_DEN=0, i_DI=0, i_DWE=0, i_RST=0, i_REL=0,
				i_CLKIN1=clkdiv, i_CLKIN2=0, i_CLKINSEL=1, i_CLKFBIN=buf_pll_fb,
				o_CLKFBOUT=buf_pll_fb, o_LOCKED=pll_lckd,
				p_CLKIN1_PERIOD=in_period,
				p_CLKIN2_PERIOD=in_period,
				p_CLKOUT0_DUTY_CYCLE=0.5, o_CLKOUT0=pllout0,
				p_CLKOUT1_DUTY_CYCLE=0.5, o_CLKOUT1=pllout1,
				p_CLKOUT2_DUTY_CYCLE=0.5, o_CLKOUT2=pllout2,
				p_CLKOUT3_DUTY_CYCLE=0.5, o_CLKOUT3=pllout3,
				p_CLKOUT4_DUTY_CYCLE=0.5, o_CLKOUT4=pllout4,
				p_CLKOUT5_DUTY_CYCLE=0.5, o_CLKOUT5=pllout5,
				p_CLKOUT0_DIVIDE=p//4*f_div, p_CLKOUT0_PHASE=0., # sdram wr, rd
				p_CLKOUT1_DIVIDE=p//8*f_div, p_CLKOUT1_PHASE=0., # tdcdtc
				p_CLKOUT2_DIVIDE=p//2*f_div, p_CLKOUT2_PHASE=270., # dqs, adr, ctrl
				p_CLKOUT3_DIVIDE=p//1*f_div, p_CLKOUT3_PHASE=0., # sys
				p_CLKOUT4_DIVIDE=p//1*f_div, p_CLKOUT4_PHASE=0., # buffered sys
				p_CLKOUT5_DIVIDE=p//2*f_div, p_CLKOUT5_PHASE=250., # off-chip ddr
			)

		self.specials += Instance("BUFPLL", p_DIVIDE=4,
				i_PLLIN=pllout0, i_GCLK=self.cd_sys.clk,
				i_LOCKED=pll_lckd, o_IOCLK=self.cd_sdram_full_wr.clk,
				o_SERDESSTROBE=self.clk4x_wr_strb)
		#self.specials += Instance("BUFPLL", p_DIVIDE=4,
		#		i_PLLIN=pllout0, i_GCLK=self.cd_sys.clk,
		#		i_LOCKED=pll_lckd, o_IOCLK=self.cd_sdram_full_rd.clk,
		#		o_SERDESSTROBE=self.clk4x_rd_strb)
		self.comb += [
			self.cd_sdram_full_rd.clk.eq(self.cd_sdram_full_wr.clk),
			self.clk4x_rd_strb.eq(self.clk4x_wr_strb),
			]

		self.specials += Instance("BUFPLL", p_DIVIDE=4,
				i_PLLIN=pllout1, i_GCLK=self.cd_sys.clk,
				i_LOCKED=pll_lckd, o_IOCLK=self.cd_tdcdtc.clk,
				o_SERDESSTROBE=self.tdcdtc_strb)

		self.specials += Instance("BUFG", i_I=pllout2, o_O=self.cd_sdram_half.clk)
		self.specials += Instance("BUFG", i_I=pllout3, o_O=self.cd_sys.clk)
		self.specials += Instance("BUFG", i_I=pllout4, o_O=self.cd_base.clk)

		clk_sdram_half_shifted = Signal()
		self.specials += Instance("BUFG", i_I=pllout5, o_O=clk_sdram_half_shifted)
		self.specials += Instance("ODDR2",
				p_DDR_ALIGNMENT="NONE", p_INIT=0, p_SRTYPE="SYNC",
				i_C0=clk_sdram_half_shifted, i_C1=~clk_sdram_half_shifted,
				i_CE=1, i_D0=1, i_D1=0, i_R=0, i_S=0,
				o_Q=pads.ddr_clk_p)
		self.specials += Instance("ODDR2",
				p_DDR_ALIGNMENT="NONE", p_INIT=0, p_SRTYPE="SYNC",
				i_C0=clk_sdram_half_shifted, i_C1=~clk_sdram_half_shifted,
				i_CE=1, i_D0=0, i_D1=1, i_R=0, i_S=0,
				o_Q=pads.ddr_clk_n)

		# Let the synthesizer insert the appropriate buffers
		self.comb += [
			self.cd_eth_rx.clk.eq(pads.eth_rx_clk),
			self.cd_eth_tx.clk.eq(pads.eth_tx_clk),
			]
