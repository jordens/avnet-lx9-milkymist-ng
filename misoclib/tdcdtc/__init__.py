from migen.fhdl.std import *
from migen.bus import wishbone
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.genlib.record import Record
from migen.genlib.fifo import SyncFIFO
from migen.genlib.coding import PriorityEncoder
from migen.bus.transactions import *

from misoclib.tdcdtc.io import TdcDtc, HiresTdcDtc


class TdcDtcHostif(Module, AutoCSR):
	def __init__(self, pads, depth_dtc=128, depth_tdc=128,
			timestamp_width=32, hires=True, wbone=True):
		pads_width = flen(pads.io)
		hires_width = 3

		if wbone:
			self.bus = bus = wishbone.Interface()
		self.trigger = Signal()
		if hires:
			self.serdes_clk = ClockSignal("tdcdtc")
			self.serdes_strb = Signal()

		self.submodules.ev = EventManager()
		self.ev.tdc_readable = EventSourceLevel()
		self.ev.dtc_writable = EventSourceLevel()
		self.ev.tdc_overflow = EventSourceProcess()
		self.ev.dtc_underflow = EventSourceProcess()
		self.ev.started = EventSourceProcess()
		self.ev.stopped = EventSourceProcess()
		self.ev.wrap = EventSourcePulse()
		self.ev.finalize()

		self._cycle = CSRStatus(timestamp_width - hires_width)
		self._zero = CSR()
		self._arm = CSRStorage()
		self._force = CSRStorage()
		self._flush_tdc = CSRStorage()
		self._flush_dtc = CSRStorage()
		self._level = CSRStatus(pads_width)
		self._up_en = CSRStorage(pads_width)
		self._down_en = CSRStorage(pads_width)
		self._out_en = CSRStorage(pads_width)
		self._tdc_time = CSRStatus(timestamp_width)
		self._tdc_data = CSRStatus(pads_width)
		self._tdc_next = CSR()
		self._dtc_time = CSRStorage(timestamp_width)
		self._dtc_data = CSRStorage(pads_width)
		self._dtc_next = CSR()

		##

		# CSR/events to FIFO interface and signals
		fifo_layout = [("time", timestamp_width), ("data", pads_width)]
		self.submodules.fifo_dtc = SyncFIFO(fifo_layout, depth_dtc)
		self.submodules.fifo_tdc = SyncFIFO(fifo_layout, depth_tdc)

		cycle = Signal(timestamp_width - hires_width)
		running = Signal()
		dtc_subcycle = Signal(hires_width)
		dtc_fire = Signal()

		self.comb += [
				self.ev.tdc_readable.trigger.eq(self.fifo_tdc.readable),
				self.ev.dtc_writable.trigger.eq(self.fifo_dtc.writable),
				self.ev.tdc_overflow.trigger.eq(~self.fifo_tdc.writable),
				self.ev.dtc_underflow.trigger.eq(~self.fifo_dtc.readable),
				self.ev.started.trigger.eq(~running),
				self.ev.stopped.trigger.eq(running),
				self.ev.wrap.trigger.eq(~cycle == 0),

				self._cycle.status.eq(cycle),
				self._tdc_time.status.eq(self.fifo_tdc.dout.time),
				self._tdc_data.status.eq(self.fifo_tdc.dout.data),
				self.fifo_dtc.din.time.eq(self._dtc_time.storage),
				self.fifo_dtc.din.data.eq(self._dtc_data.storage),

				running.eq((self._arm.storage & self.trigger) |
					self._force.storage),
				dtc_subcycle.eq(self.fifo_dtc.dout.time[:hires_width]),
				dtc_fire.eq(self.fifo_dtc.readable & running &
					(cycle == self.fifo_dtc.dout.time[hires_width:])),
				]

		self.sync += [
				If(running, cycle.eq(cycle + 1)),
				If(self._zero.re, cycle.eq(0)),
				]

		# one tdcdtc per pin
		subs = []
		for i in range(flen(pads.io)):
			io = pads.io[i]
			if hires:
				iob = None
				if hasattr(pads, "iob"):
					iob = pads.iob[i]
				s = HiresTdcDtc(io, iob, self.serdes_clk, self.serdes_strb)
			else:
				s = TdcDtc(io)
			self.submodules += s
			subs.append(s)

			self.comb += [
					s.tdc.in_en[0].eq(self._down_en.storage[i]),
					s.tdc.in_en[1].eq(self._up_en.storage[i]),
					s.dtc.out_en.eq(self._out_en.storage[i]),
					s.dtc.subcycle.eq(dtc_subcycle),
					s.dtc.level.eq(self.fifo_dtc.dout.data[i]),
					s.dtc.fire.eq(dtc_fire),
					]

		self.submodules.enc = PriorityEncoder(pads_width)

		tdc_tsps = Array([s.tdc.subcycle for s in subs])

		wbone_tdc_next = Signal()
		wbone_dtc_next = Signal()

		# connect fifos and individual tdcdtcs
		self.comb += [
				self.enc.i.eq(Cat(*(s.tdc.detect for s in subs))),
				self._level.status.eq(Cat(*(s.tdc.level for s in subs))),
				self.fifo_tdc.din.time.eq(Cat(tdc_tsps[self.enc.o], cycle)),
				self.fifo_tdc.din.data.eq(self.enc.i),

				self.fifo_tdc.we.eq(running & ~self.enc.n),
				self.fifo_tdc.re.eq(self._tdc_next.re | wbone_tdc_next |
					self._flush_tdc.storage),

				self.fifo_dtc.we.eq(self._dtc_next.re | wbone_dtc_next),
				self.fifo_dtc.re.eq(dtc_fire | self._flush_dtc.storage),
				]

		# faster low latency wishbone interface
		# slightly weird: tdc and dtc registers are the same
		# fifo pop/push is on read/write of the time register
		if wbone:
			self.sync += [
					wbone_tdc_next.eq(0),
					wbone_dtc_next.eq(0),
					bus.dat_r.eq(0),
					bus.ack.eq(0),
					If(bus.cyc & bus.stb & ~bus.ack,
						bus.ack.eq(1),
						Case(bus.adr[:8], {
							0x00: bus.dat_r.eq(cycle),
							0x10: bus.dat_r.eq(self.fifo_tdc.dout.time),
							0x11: bus.dat_r.eq(self.fifo_tdc.dout.data),
							0x20: bus.dat_r.eq(self.fifo_dtc.din.time),
							0x21: bus.dat_r.eq(self.fifo_dtc.din.data),
						}),
						If(bus.we,
							Case(bus.adr[:8], {
								0x12: wbone_tdc_next.eq(1),
								0x20: self._dtc_time.storage_full.eq(bus.dat_w),
								0x21: self._dtc_data.storage_full.eq(bus.dat_w),
								0x22: wbone_dtc_next.eq(1),
							}),
						),
					),
					]


class TB(Module):
	def __init__(self):
		self.submodules.master = wishbone.Initiator(self.gen())
		self.pads = Record([("io", 2), ("iob", 2)])
		self.i = Signal()
		self.o = Signal()
		self.comb += self.pads.io[1].eq(self.i)
		self.comb += self.o.eq(self.pads.io[0])
		self.submodules.slave = TdcDtcHostif(self.pads, hires=False)
		self.submodules.tap = wishbone.Tap(self.slave.bus)
		self.submodules.intercon = wishbone.InterconnectPointToPoint(
				self.master.bus, self.slave.bus)

	def gen(self):
		yield TRead(0x00) # status
		yield TWrite(0x00, 0x3) # arm force
		yield TWrite(0x02, 0x0) # cycle
		yield TRead(0x02) # cycle
		yield TRead(0x02) # cycle
		yield TWrite(0x08, 0x1) # en on 0
		yield TWrite(0x0a, 0x2) # up on 1
		for i in range(1, 3):
			yield TWrite(0x20, 0x115*i) # time
			yield TWrite(0x21, 0x1) # chan
			yield TWrite(0x2f, 1) # we
			yield TWrite(0x20, 0x115*i+0x030) # time
			yield TWrite(0x21, 0x0) # chan
			yield TWrite(0x2f, 1) # we
		for i in range(4):
			while True:
				t = TRead(0x01)
				yield t
				if t.data & (1<<3): # in_r
					break
				for i in range(3):
					yield None
			yield TRead(0x10) # time
			yield TRead(0x11) # chan
			yield TWrite(0x1f, 1) # re

	def do_simulation(self, s):
		cc = s.cycle_counter
		if cc < 140: pass
		elif cc < 145: s.wr(self.i, 1)
		elif cc < 150: s.wr(self.i, 0)
		elif cc < 155: s.wr(self.i, 1)
		elif cc < 160: s.wr(self.i, 0)
		elif cc < 161: s.wr(self.i, 1)
		elif cc < 162: s.wr(self.i, 0)
		elif cc < 163: s.wr(self.i, 1)
		elif cc < 164: s.wr(self.i, 0)
		s.interrupt = self.master.done


def _main():
	from migen.sim.generic import Simulator, TopLevel
	from migen.fhdl import verilog

	pads = Record([("io", 4), ("iob", 4)])
	t = TdcDtcHostif(pads, hires=True)
	#print(verilog.convert(t, ios={t.serdes_strb, pads.io, pads.iob}))

	tb = TB()
	sim = Simulator(tb, TopLevel("tdcdtc.vcd"))
	sim.run()


if __name__ == "__main__":
	_main()
