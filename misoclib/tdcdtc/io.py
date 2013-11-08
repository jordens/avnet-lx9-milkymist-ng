from migen.fhdl.std import *
from migen.genlib.coding import PriorityEncoder


class Tdc(Module):
	def __init__(self, i):
		self.detect = Signal()
		self.level = Signal()
		self.in_en = Signal(2)
		self.subcycle = Signal(3)

		active = Signal()
		self.comb += [
				active.eq((self.level & self.in_en[0]) |
					(~self.level & self.in_en[1])),
				self.detect.eq((i != self.level) & active),
				self.subcycle.eq(0),
				]
		self.sync += self.level.eq(i)


class Dtc(Module):
	def __init__(self, o, t):
		self.out_en = Signal()
		self.subcycle = Signal(3)
		self.level = Signal()
		self.fire = Signal()

		self.comb += t.eq(~self.out_en)
		self.sync += [
				If(self.fire,
					o.eq(self.level),
				),
				]


class HiresTdc(Module):
	def __init__(self, i, serdes_clk, serdes_stb):
		self.detect = Signal()
		self.level = Signal()
		self.in_en = Signal(2)
		self.subcycle = Signal(3)

		q = Signal(8)
		cascade = Signal()

		common = dict(p_BITSLIP_ENABLE="FALSE", p_DATA_RATE="SDR",
				p_DATA_WIDTH=8, p_INTERFACE_TYPE="RETIMED",
				i_BITSLIP=0, i_CE0=1,
				i_CLK0=serdes_clk, i_CLK1=0, i_CLKDIV=ClockSignal(),
				i_IOCE=serdes_stb, i_RST=0)
		self.specials.master = Instance("ISERDES2", p_SERDES_MODE="MASTER",
				o_Q4=q[7], o_Q3=q[6], o_Q2=q[5], o_Q1=q[4],
				o_SHIFTOUT=cascade, i_D=i, i_SHIFTIN=0,
				**common)
		self.specials.slave = Instance("ISERDES2", p_SERDES_MODE="SLAVE",
				o_Q4=q[3], o_Q3=q[2], o_Q2=q[1], o_Q1=q[0],
				i_D=0, i_SHIFTIN=cascade,
				**common)

		self.submodules.coder = PriorityEncoder(8)
		# let the encoder look for the first (lsb, oldest, starting) polarity change
		active = Signal()
		self.comb += [
				active.eq((self.level & self.in_en[0]) |
					(~self.level & self.in_en[1])),
				self.coder.i.eq(q ^ Replicate(self.level, 8)),
				self.detect.eq(~self.coder.n & active),
				self.subcycle.eq(self.coder.o),
				]
		self.sync += If(~self.coder.n, self.level.eq(~self.level))


class HiresDtc(Module):
	def __init__(self, o, t, serdes_clk, serdes_stb):
		self.out_en = Signal()
		self.subcycle = Signal(3)
		self.level = Signal()
		self.fire = Signal()

		q = Signal(8)
		cascade = Signal(4)
		ti = Signal()

		common = dict(p_DATA_RATE_OQ="SDR", p_DATA_RATE_OT="SDR",
				p_DATA_WIDTH=8, p_OUTPUT_MODE="DIFFERENTIAL",
				i_T4=ti, i_T3=ti, i_T2=ti, i_T1=ti, i_TRAIN=0,
				i_CLK0=serdes_clk, i_CLK1=0, i_CLKDIV=ClockSignal(),
				i_IOCE=serdes_stb, i_OCE=1, i_TCE=1, i_RST=0)
		self.specials.master = Instance("OSERDES2", p_SERDES_MODE="MASTER",
				o_OQ=o, o_TQ=t,
				i_D4=q[7], i_D3=q[6], i_D2=q[5], i_D1=q[4],
				i_SHIFTIN1=1, i_SHIFTIN2=1,
				i_SHIFTIN3=cascade[2], i_SHIFTIN4=cascade[3],
				o_SHIFTOUT1=cascade[0], o_SHIFTOUT2=cascade[1],
				**common)
		self.specials.slave = Instance("OSERDES2", p_SERDES_MODE="SLAVE",
				i_D4=q[3], i_D3=q[2], i_D2=q[1], i_D1=q[0],
				i_SHIFTIN1=cascade[0], i_SHIFTIN2=cascade[1],
				i_SHIFTIN3=1, i_SHIFTIN4=1,
				o_SHIFTOUT3=cascade[2], o_SHIFTOUT4=cascade[3],
				**common)
		
		# prepare edges to xor the current level with
		edges = Array([0xff^((1<<i) - 1) for i in range(8)])
		self.comb += ti.eq(~self.out_en)
		self.sync += [
				q.eq(Replicate(q[-1], 8)), # maintain last level
				If(self.fire & (self.level != q[-1]),
					q.eq(q ^ edges[self.subcycle]),
				),
				]


class TdcDtc(Module):
	def __init__(self, io):
		dq = TSTriple()
		self.specials.q = q = dq.get_tristate(io)
		t = Signal()
		self.comb += q.oe.eq(~t)
		self.submodules.tdc = Tdc(q.i)
		self.submodules.dtc = Dtc(q.o, t)


class HiresTdcDtc(Module):
	def __init__(self, io, iob, serdes_clk, serdes_stb):
		i, o, t = Signal(), Signal(), Signal()
		if iob is None:
			self.specials.iobufds = Instance("IOBUF",
					i_T=t, o_O=i, i_I=o, io_IO=io)
		else:
			self.specials.iobufds = Instance("IOBUFDS",
					i_T=t, o_O=i, i_I=o, io_IO=io, io_IOB=iob)
		self.submodules.tdc = HiresTdc(i, serdes_clk, serdes_stb)
		self.submodules.dtc = HiresDtc(o, t, serdes_clk, serdes_stb)
