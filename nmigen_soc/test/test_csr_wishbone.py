# nmigen: UnusedElaboratable=no

import unittest
from nmigen import *
from nmigen.back.pysim import *

from .. import csr
from ..csr.wishbone import *


class MockRegister(Elaboratable):
    def __init__(self, width):
        self.element = csr.Element(width, "rw")
        self.r_count = Signal(8)
        self.w_count = Signal(8)
        self.data    = Signal(width)

    def elaborate(self, platform):
        m = Module()

        with m.If(self.element.r_stb):
            m.d.sync += self.r_count.eq(self.r_count + 1)
        m.d.comb += self.element.r_data.eq(self.data)

        with m.If(self.element.w_stb):
            m.d.sync += self.w_count.eq(self.w_count + 1)
            m.d.sync += self.data.eq(self.element.w_data)

        return m


class WishboneCSRBridgeTestCase(unittest.TestCase):
    def test_wrong_csr_bus(self):
        with self.assertRaisesRegex(ValueError,
                r"CSR bus must be an instance of CSRInterface, not 'foo'"):
            WishboneCSRBridge(csr_bus="foo")

    def test_wrong_csr_bus_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"CSR bus data width must be one of 8, 16, 32, 64, not 7"):
            WishboneCSRBridge(csr_bus=csr.Interface(addr_width=10, data_width=7))

    def test_narrow_mock(self):
        mux   = csr.Multiplexer(addr_width=10, data_width=8)
        reg_1 = MockRegister(8)
        mux.add(reg_1.element)
        reg_2 = MockRegister(16)
        mux.add(reg_2.element)
        dut   = WishboneCSRBridge(mux.bus)

        def sim_test():
            yield dut.wb_bus.cyc.eq(1)
            yield dut.wb_bus.sel.eq(0b1)

            yield dut.wb_bus.we.eq(1)

            yield dut.wb_bus.adr.eq(0)
            yield dut.wb_bus.stb.eq(1)
            yield dut.wb_bus.dat_w.eq(0x55)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield reg_1.r_count), 0)
            self.assertEqual((yield reg_1.w_count), 1)
            self.assertEqual((yield reg_1.data), 0x55)
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

            yield dut.wb_bus.adr.eq(1)
            yield dut.wb_bus.stb.eq(1)
            yield dut.wb_bus.dat_w.eq(0xaa)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield reg_2.r_count), 0)
            self.assertEqual((yield reg_2.w_count), 0)
            self.assertEqual((yield reg_2.data), 0)
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

            yield dut.wb_bus.adr.eq(2)
            yield dut.wb_bus.stb.eq(1)
            yield dut.wb_bus.dat_w.eq(0xbb)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield reg_2.r_count), 0)
            self.assertEqual((yield reg_2.w_count), 1)
            self.assertEqual((yield reg_2.data), 0xbbaa)
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

            yield dut.wb_bus.we.eq(0)

            yield dut.wb_bus.adr.eq(0)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0x55)
            self.assertEqual((yield reg_1.r_count), 1)
            self.assertEqual((yield reg_1.w_count), 1)
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

            yield dut.wb_bus.adr.eq(1)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0xaa)
            self.assertEqual((yield reg_2.r_count), 1)
            self.assertEqual((yield reg_2.w_count), 1)
            yield dut.wb_bus.stb.eq(0)
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

            yield reg_2.data.eq(0x33333)

            yield dut.wb_bus.adr.eq(2)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0xbb)
            self.assertEqual((yield reg_2.r_count), 1)
            self.assertEqual((yield reg_2.w_count), 1)
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

        m = Module()
        m.submodules += mux, reg_1, reg_2, dut
        with Simulator(m, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()

    def test_wide_mock(self):
        mux = csr.Multiplexer(addr_width=10, data_width=8)
        reg = MockRegister(32)
        mux.add(reg.element)
        dut = WishboneCSRBridge(mux.bus, data_width=32)

        def sim_test():
            yield dut.wb_bus.cyc.eq(1)
            yield dut.wb_bus.adr.eq(0)

            yield dut.wb_bus.we.eq(1)

            yield dut.wb_bus.dat_w.eq(0x44332211)
            yield dut.wb_bus.sel.eq(0b1111)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield reg.r_count), 0)
            self.assertEqual((yield reg.w_count), 1)
            self.assertEqual((yield reg.data), 0x44332211)
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

            # partial write
            yield dut.wb_bus.dat_w.eq(0xaabbccdd)
            yield dut.wb_bus.sel.eq(0b0110)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield reg.r_count), 0)
            self.assertEqual((yield reg.w_count), 1)
            self.assertEqual((yield reg.data), 0x44332211)
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

            yield dut.wb_bus.we.eq(0)

            yield dut.wb_bus.sel.eq(0b1111)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0x44332211)
            self.assertEqual((yield reg.r_count), 1)
            self.assertEqual((yield reg.w_count), 1)
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

            yield reg.data.eq(0xaaaaaaaa)

            # partial read
            yield dut.wb_bus.sel.eq(0b0110)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0x00332200)
            self.assertEqual((yield reg.r_count), 1)
            self.assertEqual((yield reg.w_count), 1)
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

        m = Module()
        m.submodules += mux, reg, dut
        with Simulator(m, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()

    def test_wide_dsl(self):
        # The following 31-bit register has the following layout:
        # bits [    0] : empty, represented by 0
        # bits [16: 1] : field "value1"
        # bits [30:17] : field "value2"
        # Note that this register does NOT have bit 31
        reg = csr.Register("dsl", "rw", fields=[
            csr.Field("value1", width=16, startbit=1),
            csr.Field("value2", width=14, startbit=17)
        ])
        bank = csr.Bank(addr_width=3, data_width=8, type="dec")
        with bank:
            bank.r += reg
        dut = WishboneCSRBridge(bank.dec.bus, data_width=32)

        def sim_test():
            yield dut.wb_bus.cyc.eq(1)
            yield dut.wb_bus.adr.eq(0)

            yield dut.wb_bus.we.eq(1)

            yield dut.wb_bus.dat_w.eq(0x44332211)
            yield dut.wb_bus.sel.eq(0b1111)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield reg[:]), 0x44332211)
            self.assertEqual((yield reg.f.value1[:]), (0x44332211 >> 1) & (2**16 - 1))
            self.assertEqual((yield reg.f.value2[:]), (0x44332211 >> 17) & (2**14 - 1))
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

            # partial write
            yield dut.wb_bus.dat_w.eq(0xaabbccdd)
            yield dut.wb_bus.sel.eq(0b0110)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield reg[:]), 0x44332211)
            self.assertEqual((yield reg.f.value1[:]), (0x44332211 >> 1) & (2**16 - 1))
            self.assertEqual((yield reg.f.value2[:]), (0x44332211 >> 17) & (2**14 - 1))
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

            yield dut.wb_bus.we.eq(0)

            yield dut.wb_bus.sel.eq(0b1111)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0x44332211)
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

            yield reg.s.eq(0xaaaaaaaa)

            # partial read
            yield dut.wb_bus.sel.eq(0b0110)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0x00332200)
            yield dut.wb_bus.stb.eq(0)                      # Only deassert STB when ACK is low
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)

        m = Module()
        m.submodules += bank, dut
        with Simulator(m, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()
