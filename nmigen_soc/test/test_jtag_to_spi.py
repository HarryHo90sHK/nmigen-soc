import unittest
from nmigen import *
from nmigen.back.pysim import *

from ..jtag_to_spi import *


class JTAGtoSPITestCase(unittest.TestCase):
    """Note: directly adapted from https://github.com/quartiq/bscan_spi_bitstreams/blob/master/xilinx_bscan_spi.py
    """

    def setUp(self):
        self.bits = 8
        self.dut = JTAGtoSPI(bits=self.bits)

    def test_initial_conditions(self):
        def check():
            yield
            self.assertEqual((yield self.dut.cs_n.oe), 0)
            self.assertEqual((yield self.dut.mosi.oe), 0)
            self.assertEqual((yield self.dut.miso.oe), 0)
            self.assertEqual((yield self.dut.clk.oe), 0)
        with Simulator(self.dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(check())
            sim.run()

    def test_enable(self):
        def check():
            yield self.dut.jtag.sel.eq(1)
            yield self.dut.jtag.shift.eq(1)
            yield
            self.assertEqual((yield self.dut.cs_n.oe), 1)
            self.assertEqual((yield self.dut.mosi.oe), 1)
            self.assertEqual((yield self.dut.miso.oe), 0)
            self.assertEqual((yield self.dut.clk.oe), 1)
        with Simulator(self.dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(check())
            sim.run()

    def run_seq(self, tdi, tdo, spi=None):
        yield self.dut.jtag.sel.eq(1)
        yield
        yield self.dut.jtag.shift.eq(1)
        for di in tdi:
            yield self.dut.jtag.tdi.eq(di)
            yield
            tdo.append((yield self.dut.jtag.tdo))
            if spi is not None:
                v = []
                for k in "cs_n clk mosi miso".split():
                    t = getattr(self.dut, k)
                    v.append("{}>".format((yield t.o)) if (yield t.oe)
                            else "<{}".format((yield t.i)))
                spi.append(" ".join(v))
        yield self.dut.jtag.sel.eq(0)
        yield
        yield self.dut.jtag.shift.eq(0)
        yield

    def test_shift(self):
        bits = 8
        data = 0x81
        tdi = [0, 0, 1]  # dummy from BYPASS TAPs and marker
        tdi += [((bits - 1) >> j) & 1 for j in range(self.bits - 1, -1, -1)]
        tdi += [(data >> j) & 1 for j in range(bits)]
        tdi += [0, 0, 0, 0]  # dummy from BYPASS TAPs
        tdo = []
        spi = []
        with Simulator(self.dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(self.run_seq(tdi, tdo, spi))
            sim.run()
        # print(tdo)
        for l in spi:
            print(l)
