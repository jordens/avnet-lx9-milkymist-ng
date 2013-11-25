from migen.fhdl.std import *
from migen.bus.transactions import *
from migen.bus import wishbone
from migen.genlib.misc import timeline
from migen.genlib.record import Record


class SpiFlash(Module):
	def __init__(self, pads, cmd=0xfffefeff, cmd_width=32, addr_width=24,
			dummy=10, div=2):
		"""
		Simple read-only SPI flash, e.g. N25Q128 on the LX9 Microboard.

		Supports multi-bit pseudo-parallel reads (aka Dual or Quad I/O Fast
		Read). Only supports mode0 (cpol=0, cpha=0).

		`cmd` is the read instruction. Since everything is transmitted on all
		dq lines (cmd, adr and data), extend/interleave cmd to full pads.dq
		width even if dq1-dq3 are don't care during the command phase:
		For example, for N25Q128, 0xeb is the quad i/o fast read, and
		extended to 4 bits (dq1,dq2,dq3 high) is: 0xfffefeff
		"""
		self.bus = bus = wishbone.Interface()

		##

		wbone_width = flen(bus.dat_r)
		spi_width = flen(pads.dq)

		pads.cs_n.reset = 1

		dq = TSTriple(spi_width)
		self.specials.dq = dq.get_tristate(pads.dq)

		sr = Signal(max(cmd_width, addr_width, wbone_width))
		self.comb += [
				bus.dat_r.eq(sr[:wbone_width]),
				dq.o.eq(sr[-spi_width:]),
				]

		if div == 1:
			i = 0
			self.comb += pads.clk.eq(~ClockSignal())
			self.sync += sr.eq(Cat(dq.i, sr[:-spi_width]))
		else:
			i = Signal(max=div)
			self.sync += [
					i.eq(i + 1),
					If(i == div//2 - 1,
						pads.clk.eq(1),
					),
					If(i == div - 1,
						i.eq(0),
						pads.clk.eq(0),
						sr.eq(Cat(dq.i, sr[:-spi_width]))
					),
				]

		# spi is byte-addressed, prefix by zeros
		z = Replicate(0, log2_int(wbone_width//8))

		seq = [
			(cmd_width//spi_width*div,
				[dq.oe.eq(1), pads.cs_n.eq(0), sr[-cmd_width:].eq(cmd)]),
			(addr_width//spi_width*div,
				[sr[-addr_width:].eq(Cat(z, bus.adr))]),
			((dummy + wbone_width//spi_width)*div,
				[dq.oe.eq(0)]),
			(1,
				[bus.ack.eq(1), pads.cs_n.eq(1)]),
			(1, # tSHSL!
				[bus.ack.eq(0)]),
			(0,
				[]),
		]

		# accumulate timeline deltas
		t, tseq = 0, []
		for dt, a in seq:
			tseq.append((t, a))
			t += dt

		self.sync += timeline(bus.cyc & bus.stb & (i == div - 1), tseq)



class SpiFlashTB(Module):
	def __init__(self):
		self.submodules.master = wishbone.Initiator(self.gen_reads())
		self.pads = Record([("cs_n", 1), ("clk", 1), ("dq", 4)])
		self.submodules.slave = SpiFlash(self.pads)
		self.submodules.tap = wishbone.Tap(self.slave.bus)
		self.submodules.intercon = wishbone.InterconnectPointToPoint(
				self.master.bus, self.slave.bus)
		self.cycle = 0

	def gen_reads(self):
		for a in range(10):
			t = TRead(a)
			yield t
			print("read {} in {} cycles(s)".format(t.data, t.latency))

	def do_simulation(self, s):
		if s.rd(self.pads.cs_n):
			self.cycle = 0
		else:
			self.cycle += 1
			if not s.rd(self.slave.dq.oe):
				s.wr(self.slave.dq.i, self.cycle & 0xf)
		s.interrupt = self.master.done


def _main():
	from migen.sim.generic import Simulator, TopLevel
	from migen.fhdl import verilog

	pads = Record([("cs_n", 1), ("clk", 1), ("dq", 4)])
	s = SpiFlash(pads)
	print(verilog.convert(s, ios={pads.clk, pads.cs_n, pads.dq, s.bus.adr,
		s.bus.dat_r, s.bus.cyc, s.bus.ack, s.bus.stb}))

	tb = SpiFlashTB()
	sim = Simulator(tb, TopLevel("spiflash.vcd"))
	sim.run()


if __name__ == "__main__":
	_main()
