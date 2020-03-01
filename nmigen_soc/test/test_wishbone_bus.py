# nmigen: UnusedElaboratable=no

import unittest
from nmigen import *
from nmigen.hdl.rec import *
from nmigen.back.pysim import *

from ..wishbone import *


class InterfaceTestCase(unittest.TestCase):
    def test_simple(self):
        iface = Interface(addr_width=32, data_width=8)
        self.assertEqual(iface.addr_width, 32)
        self.assertEqual(iface.data_width, 8)
        self.assertEqual(iface.granularity, 8)
        self.assertEqual(iface.memory_map.addr_width, 32)
        self.assertEqual(iface.memory_map.data_width, 8)
        self.assertEqual(iface.layout, Layout.cast([
            ("adr",   32, DIR_FANOUT),
            ("dat_w", 8,  DIR_FANOUT),
            ("dat_r", 8,  DIR_FANIN),
            ("sel",   1,  DIR_FANOUT),
            ("cyc",   1,  DIR_FANOUT),
            ("stb",   1,  DIR_FANOUT),
            ("we",    1,  DIR_FANOUT),
            ("ack",   1,  DIR_FANIN),
        ]))

    def test_granularity(self):
        iface = Interface(addr_width=30, data_width=32, granularity=8)
        self.assertEqual(iface.addr_width, 30)
        self.assertEqual(iface.data_width, 32)
        self.assertEqual(iface.granularity, 8)
        self.assertEqual(iface.memory_map.addr_width, 32)
        self.assertEqual(iface.memory_map.data_width, 8)
        self.assertEqual(iface.layout, Layout.cast([
            ("adr",   30, DIR_FANOUT),
            ("dat_w", 32, DIR_FANOUT),
            ("dat_r", 32, DIR_FANIN),
            ("sel",   4,  DIR_FANOUT),
            ("cyc",   1,  DIR_FANOUT),
            ("stb",   1,  DIR_FANOUT),
            ("we",    1,  DIR_FANOUT),
            ("ack",   1,  DIR_FANIN),
        ]))

    def test_features(self):
        iface = Interface(addr_width=32, data_width=32,
                          features={"rty", "err", "stall", "lock", "cti", "bte"})
        self.assertEqual(iface.layout, Layout.cast([
            ("adr",   32, DIR_FANOUT),
            ("dat_w", 32, DIR_FANOUT),
            ("dat_r", 32, DIR_FANIN),
            ("sel",   1,  DIR_FANOUT),
            ("cyc",   1,  DIR_FANOUT),
            ("stb",   1,  DIR_FANOUT),
            ("we",    1,  DIR_FANOUT),
            ("ack",   1,  DIR_FANIN),
            ("err",   1,  DIR_FANIN),
            ("rty",   1,  DIR_FANIN),
            ("stall", 1,  DIR_FANIN),
            ("lock",  1,  DIR_FANOUT),
            ("cti",   CycleType,    DIR_FANOUT),
            ("bte",   BurstTypeExt, DIR_FANOUT),
        ]))

    def test_wrong_addr_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Address width must be a non-negative integer, not -1"):
            Interface(addr_width=-1, data_width=8)

    def test_wrong_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Data width must be one of 8, 16, 32, 64, not 7"):
            Interface(addr_width=0, data_width=7)

    def test_wrong_granularity(self):
        with self.assertRaisesRegex(ValueError,
                r"Granularity must be one of 8, 16, 32, 64, not 7"):
            Interface(addr_width=0, data_width=32, granularity=7)

    def test_wrong_granularity_wide(self):
        with self.assertRaisesRegex(ValueError,
                r"Granularity 32 may not be greater than data width 8"):
            Interface(addr_width=0, data_width=8, granularity=32)

    def test_wrong_features(self):
        with self.assertRaisesRegex(ValueError,
                r"Optional signal\(s\) 'foo' are not supported"):
            Interface(addr_width=0, data_width=8, features={"foo"})


class DecoderTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = Decoder(addr_width=31, data_width=32, granularity=16)

    def test_add_align_to(self):
        sub_1 = Interface(addr_width=15, data_width=32, granularity=16)
        sub_2 = Interface(addr_width=15, data_width=32, granularity=16)
        self.assertEqual(self.dut.add(sub_1), (0x00000000, 0x00010000, 1))
        self.assertEqual(self.dut.align_to(18), 0x000040000)
        self.assertEqual(self.dut.add(sub_2), (0x00040000, 0x00050000, 1))

    def test_add_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Subordinate bus must be an instance of wishbone\.Interface, not 'foo'"):
            self.dut.add("foo")

    def test_add_wrong_granularity(self):
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has granularity 32, which is greater than "
                r"the decoder granularity 16"):
            self.dut.add(Interface(addr_width=15, data_width=32, granularity=32))

    def test_add_wrong_width_dense(self):
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has data width 16, which is not the same as decoder "
                r"data width 32 \(required for dense address translation\)"):
            self.dut.add(Interface(addr_width=15, data_width=16, granularity=16))

    def test_add_wrong_granularity_sparse(self):
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has data width 64, which is not the same as subordinate "
                r"bus granularity 16 \(required for sparse address translation\)"):
            self.dut.add(Interface(addr_width=15, data_width=64, granularity=16), sparse=True)

    def test_add_wrong_optional_output(self):
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has optional output 'err', but the decoder does "
                r"not have a corresponding input"):
            self.dut.add(Interface(addr_width=15, data_width=32, granularity=16, features={"err"}))


class DecoderSimulationTestCase(unittest.TestCase):
    def test_simple(self):
        dut = Decoder(addr_width=30, data_width=32, granularity=8,
                      features={"err", "rty", "stall", "lock", "cti", "bte"})
        sub_1 = Interface(addr_width=14, data_width=32, granularity=8)
        self.assertEqual(dut.add(sub_1, addr=0x10000),
                         (0x10000, 0x20000, 1))
        sub_2 = Interface(addr_width=14, data_width=32, granularity=8,
                          features={"err", "rty", "stall", "lock", "cti", "bte"})
        self.assertEqual(dut.add(sub_2),
                         (0x20000, 0x30000, 1))

        def sim_test():
            yield dut.bus.adr.eq(0x10400 >> 2)
            yield dut.bus.cyc.eq(1)
            yield dut.bus.stb.eq(1)
            yield dut.bus.sel.eq(0b11)
            yield dut.bus.dat_w.eq(0x12345678)
            yield dut.bus.lock.eq(1)
            yield dut.bus.cti.eq(CycleType.INCR_BURST)
            yield dut.bus.bte.eq(BurstTypeExt.WRAP_4)
            yield sub_1.ack.eq(1)
            yield sub_1.dat_r.eq(0xabcdef01)
            yield sub_2.dat_r.eq(0x5678abcd)
            yield Delay(1e-6)
            self.assertEqual((yield sub_1.adr), 0x400 >> 2)
            self.assertEqual((yield sub_1.cyc), 1)
            self.assertEqual((yield sub_2.cyc), 0)
            self.assertEqual((yield sub_1.stb), 1)
            self.assertEqual((yield sub_1.sel), 0b11)
            self.assertEqual((yield sub_1.dat_w), 0x12345678)
            self.assertEqual((yield dut.bus.ack), 1)
            self.assertEqual((yield dut.bus.err), 0)
            self.assertEqual((yield dut.bus.rty), 0)
            self.assertEqual((yield dut.bus.dat_r), 0xabcdef01)

            yield dut.bus.adr.eq(0x20400 >> 2)
            yield dut.bus.sel.eq(0b1001)
            yield dut.bus.we.eq(1)
            yield sub_1.dat_r.eq(0)
            yield sub_1.ack.eq(0)
            yield sub_2.err.eq(1)
            yield sub_2.rty.eq(1)
            yield sub_2.stall.eq(1)
            yield Delay(1e-6)
            self.assertEqual((yield sub_2.adr), 0x400 >> 2)
            self.assertEqual((yield sub_1.cyc), 0)
            self.assertEqual((yield sub_2.cyc), 1)
            self.assertEqual((yield sub_1.stb), 1)
            self.assertEqual((yield sub_1.sel), 0b1001)
            self.assertEqual((yield sub_1.dat_w), 0x12345678)
            self.assertEqual((yield sub_2.stb), 1)
            self.assertEqual((yield sub_2.sel), 0b1001)
            self.assertEqual((yield sub_2.dat_w), 0x12345678)
            self.assertEqual((yield sub_2.lock), 1)
            self.assertEqual((yield sub_2.cti), CycleType.INCR_BURST.value)
            self.assertEqual((yield sub_2.bte), BurstTypeExt.WRAP_4.value)
            self.assertEqual((yield dut.bus.ack), 0)
            self.assertEqual((yield dut.bus.err), 1)
            self.assertEqual((yield dut.bus.rty), 1)
            self.assertEqual((yield dut.bus.stall), 1)
            self.assertEqual((yield dut.bus.dat_r), 0x5678abcd)

            yield dut.bus.adr.eq(0x10400 >> 2)
            yield dut.bus.sel.eq(0)
            yield dut.bus.cyc.eq(0)
            yield dut.bus.stb.eq(0)
            yield dut.bus.dat_w.eq(0x87654321)
            yield dut.bus.we.eq(0)
            yield Delay(1e-6)
            self.assertEqual((yield sub_1.adr), 0x400 >> 2)
            self.assertEqual((yield sub_1.cyc), 0)
            self.assertEqual((yield sub_2.cyc), 0)
            self.assertEqual((yield sub_1.stb), 0)
            self.assertEqual((yield sub_1.sel), 0)
            self.assertEqual((yield sub_1.dat_w), 0x87654321)
            self.assertEqual((yield sub_2.stb), 0)
            self.assertEqual((yield sub_2.sel), 0)
            self.assertEqual((yield sub_2.dat_w), 0x87654321)
            self.assertEqual((yield dut.bus.ack), 0)
            self.assertEqual((yield dut.bus.dat_r), 0)

        with Simulator(dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_process(sim_test())
            sim.run()

    def test_addr_translate(self):
        class AddressLoopback(Elaboratable):
            def __init__(self, **kwargs):
                self.bus = Interface(**kwargs)

            def elaborate(self, platform):
                m = Module()

                for index, sel_bit in enumerate(self.bus.sel):
                    with m.If(sel_bit):
                        segment = self.bus.dat_r.word_select(index, self.bus.granularity)
                        m.d.comb += segment.eq(self.bus.adr + index)

                return m

        dut = Decoder(addr_width=20, data_width=32, granularity=16)
        loop_1 = AddressLoopback(addr_width=7, data_width=32, granularity=16)
        self.assertEqual(dut.add(loop_1.bus, addr=0x10000),
                         (0x10000, 0x10100, 1))
        loop_2 = AddressLoopback(addr_width=6, data_width=32, granularity=8)
        self.assertEqual(dut.add(loop_2.bus, addr=0x20000),
                         (0x20000, 0x20080, 2))
        loop_3 = AddressLoopback(addr_width=8, data_width=16, granularity=16)
        self.assertEqual(dut.add(loop_3.bus, addr=0x30000, sparse=True),
                         (0x30000, 0x30100, 1))
        loop_4 = AddressLoopback(addr_width=8, data_width=8,  granularity=8)
        self.assertEqual(dut.add(loop_4.bus, addr=0x40000, sparse=True),
                         (0x40000, 0x40100, 1))

        for sig in ["adr", "dat_r", "sel"]:
            getattr(dut.bus, sig).name = "dec__" + sig
            getattr(loop_1.bus, sig).name = "sub1__" + sig
            getattr(loop_2.bus, sig).name = "sub2__" + sig
            getattr(loop_3.bus, sig).name = "sub3__" + sig
            getattr(loop_4.bus, sig).name = "sub4__" + sig

        def sim_test():
            yield dut.bus.cyc.eq(1)

            yield dut.bus.adr.eq(0x10010 >> 1)

            yield dut.bus.sel.eq(0b11)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x00090008)

            yield dut.bus.sel.eq(0b01)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x00000008)

            yield dut.bus.sel.eq(0b10)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x00090000)

            yield dut.bus.adr.eq(0x20010 >> 1)

            yield dut.bus.sel.eq(0b11)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x13121110)

            yield dut.bus.sel.eq(0b01)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x00001110)

            yield dut.bus.sel.eq(0b10)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x13120000)

            yield dut.bus.adr.eq(0x30010 >> 1)

            yield dut.bus.sel.eq(0b11)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x0008)

            yield dut.bus.sel.eq(0b01)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x0008)

            yield dut.bus.sel.eq(0b10)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x0000)

            yield dut.bus.adr.eq(0x30012 >> 1)

            yield dut.bus.sel.eq(0b11)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x0009)

            yield dut.bus.adr.eq(0x40010 >> 1)

            yield dut.bus.sel.eq(0b11)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x08)

            yield dut.bus.sel.eq(0b01)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x08)

            yield dut.bus.sel.eq(0b10)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x00)

            yield dut.bus.adr.eq(0x40012 >> 1)

            yield dut.bus.sel.eq(0b11)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x09)

        m = Module()
        m.submodules += dut, loop_1, loop_2, loop_3, loop_4
        with Simulator(m, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_process(sim_test())
            sim.run()


class ArbiterTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = Arbiter(addr_width=31, data_width=32, granularity=16)

    def test_add_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Initiator bus must be an instance of wishbone\.Interface, not 'foo'"):
            self.dut.add("foo")

    def test_add_wrong_addr_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Initiator bus has address width 15, which is not the same as arbiter "
                r"address width 31"):
            self.dut.add(Interface(addr_width=15, data_width=32, granularity=16))

    def test_add_wrong_granularity(self):
        with self.assertRaisesRegex(ValueError,
                r"Initiator bus has granularity 8, which is lesser than "
                r"the arbiter granularity 16"):
            self.dut.add(Interface(addr_width=31, data_width=32, granularity=8))

    def test_add_wrong_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Initiator bus has data width 16, which is not the same as arbiter "
                r"data width 32"):
            self.dut.add(Interface(addr_width=31, data_width=16, granularity=16))

    def test_add_wrong_optional_output(self):
        with self.assertRaisesRegex(ValueError,
                r"Initiator bus has optional output 'lock', but the arbiter does "
                r"not have a corresponding input"):
            self.dut.add(Interface(addr_width=31, data_width=32, granularity=16,
                                   features={"lock"}))


class ArbiterSimulationTestCase(unittest.TestCase):
    def test_simple(self):
        dut = Arbiter(addr_width=30, data_width=32, granularity=8,
                      features={"err", "rty", "stall", "lock", "cti", "bte"})
        itor_1 = Interface(addr_width=30, data_width=32, granularity=8)
        dut.add(itor_1)
        itor_2 = Interface(addr_width=30, data_width=32, granularity=16,
                           features={"err", "rty", "stall", "lock", "cti", "bte"})
        dut.add(itor_2)

        def sim_test():
            yield itor_1.adr.eq(0x7ffffffc >> 2)
            yield itor_1.cyc.eq(1)
            yield itor_1.stb.eq(1)
            yield itor_1.sel.eq(0b1111)
            yield itor_1.we.eq(1)
            yield itor_1.dat_w.eq(0x12345678)
            yield dut.bus.dat_r.eq(0xabcdef01)
            yield dut.bus.ack.eq(1)
            yield Delay(1e-7)
            self.assertEqual((yield dut.bus.adr), 0x7ffffffc >> 2)
            self.assertEqual((yield dut.bus.cyc), 1)
            self.assertEqual((yield dut.bus.stb), 1)
            self.assertEqual((yield dut.bus.sel), 0b1111)
            self.assertEqual((yield dut.bus.we), 1)
            self.assertEqual((yield dut.bus.dat_w), 0x12345678)
            self.assertEqual((yield dut.bus.lock), 1)
            self.assertEqual((yield dut.bus.cti), CycleType.CLASSIC.value)
            self.assertEqual((yield dut.bus.bte), BurstTypeExt.LINEAR.value)
            self.assertEqual((yield itor_1.dat_r), 0xabcdef01)
            self.assertEqual((yield itor_1.ack), 1)

            yield itor_1.cyc.eq(0)
            yield itor_2.adr.eq(0xe0000000 >> 2)
            yield itor_2.cyc.eq(1)
            yield itor_2.stb.eq(1)
            yield itor_2.sel.eq(0b10)
            yield itor_2.we.eq(0)
            yield itor_2.dat_w.eq(0x43218765)
            yield itor_2.lock.eq(0)
            yield itor_2.cti.eq(CycleType.INCR_BURST)
            yield itor_2.bte.eq(BurstTypeExt.WRAP_4)
            yield Tick()

            yield dut.bus.err.eq(1)
            yield dut.bus.rty.eq(1)
            yield dut.bus.stall.eq(0)
            yield Delay(1e-7)
            self.assertEqual((yield dut.bus.adr), 0xe0000000 >> 2)
            self.assertEqual((yield dut.bus.cyc), 1)
            self.assertEqual((yield dut.bus.stb), 1)
            self.assertEqual((yield dut.bus.sel), 0b1100)
            self.assertEqual((yield dut.bus.we), 0)
            self.assertEqual((yield dut.bus.dat_w), 0x43218765)
            self.assertEqual((yield dut.bus.lock), 0)
            self.assertEqual((yield dut.bus.cti), CycleType.INCR_BURST.value)
            self.assertEqual((yield dut.bus.bte), BurstTypeExt.WRAP_4.value)
            self.assertEqual((yield itor_2.dat_r), 0xabcdef01)
            self.assertEqual((yield itor_2.ack), 1)
            self.assertEqual((yield itor_2.err), 1)
            self.assertEqual((yield itor_2.rty), 1)
            self.assertEqual((yield itor_2.stall), 0)

        with Simulator(dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()

    def test_lock(self):
        dut = Arbiter(addr_width=30, data_width=32, features={"lock"})
        itor_1 = Interface(addr_width=30, data_width=32, features={"lock"})
        dut.add(itor_1)
        itor_2 = Interface(addr_width=30, data_width=32, features={"lock"})
        dut.add(itor_2)

        def sim_test():
            yield itor_1.cyc.eq(1)
            yield itor_1.lock.eq(1)
            yield itor_2.cyc.eq(1)
            yield dut.bus.ack.eq(1)
            yield Delay(1e-7)
            self.assertEqual((yield itor_1.ack), 1)
            self.assertEqual((yield itor_2.ack), 0)

            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield itor_1.ack), 1)
            self.assertEqual((yield itor_2.ack), 0)

            yield itor_1.lock.eq(0)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield itor_1.ack), 0)
            self.assertEqual((yield itor_2.ack), 1)

            yield itor_2.cyc.eq(0)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield itor_1.ack), 1)
            self.assertEqual((yield itor_2.ack), 0)

            yield itor_1.stb.eq(1)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield itor_1.ack), 1)
            self.assertEqual((yield itor_2.ack), 0)

            yield itor_1.stb.eq(0)
            yield itor_2.cyc.eq(1)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield itor_1.ack), 0)
            self.assertEqual((yield itor_2.ack), 1)

        with Simulator(dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()

    def test_stall(self):
        dut = Arbiter(addr_width=30, data_width=32, features={"stall"})
        itor_1 = Interface(addr_width=30, data_width=32, features={"stall"})
        dut.add(itor_1)
        itor_2 = Interface(addr_width=30, data_width=32, features={"stall"})
        dut.add(itor_2)

        def sim_test():
            yield itor_1.cyc.eq(1)
            yield itor_2.cyc.eq(1)
            yield dut.bus.stall.eq(0)
            yield Delay(1e-6)
            self.assertEqual((yield itor_1.stall), 0)
            self.assertEqual((yield itor_2.stall), 1)

            yield dut.bus.stall.eq(1)
            yield Delay(1e-6)
            self.assertEqual((yield itor_1.stall), 1)
            self.assertEqual((yield itor_2.stall), 1)

        with Simulator(dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_process(sim_test())
            sim.run()

    def test_stall_compat(self):
        dut = Arbiter(addr_width=30, data_width=32)
        itor_1 = Interface(addr_width=30, data_width=32, features={"stall"})
        dut.add(itor_1)
        itor_2 = Interface(addr_width=30, data_width=32, features={"stall"})
        dut.add(itor_2)

        def sim_test():
            yield itor_1.cyc.eq(1)
            yield itor_2.cyc.eq(1)
            yield Delay(1e-6)
            self.assertEqual((yield itor_1.stall), 1)
            self.assertEqual((yield itor_2.stall), 1)

            yield dut.bus.ack.eq(1)
            yield Delay(1e-6)
            self.assertEqual((yield itor_1.stall), 0)
            self.assertEqual((yield itor_2.stall), 1)

        with Simulator(dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_process(sim_test())
            sim.run()

    def test_roundrobin(self):
        dut = Arbiter(addr_width=30, data_width=32)
        itor_1 = Interface(addr_width=30, data_width=32)
        dut.add(itor_1)
        itor_2 = Interface(addr_width=30, data_width=32)
        dut.add(itor_2)
        itor_3 = Interface(addr_width=30, data_width=32)
        dut.add(itor_3)

        def sim_test():
            yield itor_1.cyc.eq(1)
            yield itor_2.cyc.eq(0)
            yield itor_3.cyc.eq(1)
            yield dut.bus.ack.eq(1)
            yield Delay(1e-7)
            self.assertEqual((yield itor_1.ack), 1)
            self.assertEqual((yield itor_2.ack), 0)
            self.assertEqual((yield itor_3.ack), 0)

            yield itor_1.cyc.eq(0)
            yield itor_2.cyc.eq(0)
            yield itor_3.cyc.eq(1)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield itor_1.ack), 0)
            self.assertEqual((yield itor_2.ack), 0)
            self.assertEqual((yield itor_3.ack), 1)

            yield itor_1.cyc.eq(1)
            yield itor_2.cyc.eq(1)
            yield itor_3.cyc.eq(0)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield itor_1.ack), 1)
            self.assertEqual((yield itor_2.ack), 0)
            self.assertEqual((yield itor_3.ack), 0)

            yield itor_1.cyc.eq(0)
            yield itor_2.cyc.eq(1)
            yield itor_3.cyc.eq(1)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield itor_1.ack), 0)
            self.assertEqual((yield itor_2.ack), 1)
            self.assertEqual((yield itor_3.ack), 0)

            yield itor_1.cyc.eq(1)
            yield itor_2.cyc.eq(0)
            yield itor_3.cyc.eq(1)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield itor_1.ack), 0)
            self.assertEqual((yield itor_2.ack), 0)
            self.assertEqual((yield itor_3.ack), 1)

        with Simulator(dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()


class InterconnectSharedSimulationTestCase(unittest.TestCase):
    def setUp(self):
        self.shared = Interface(addr_width=30,
                                data_width=32,
                                granularity=8,
                                features={"err","cti","bte"},
                                name="shared")
        self.master01 = Interface(addr_width=30,
                                  data_width=32,
                                  granularity=8,
                                  features={"err","cti","bte"},
                                  name="master01")
        self.master02 = Record([
            ("adr",   30, DIR_FANOUT),
            ("dat_w", 32, DIR_FANOUT),
            ("dat_r", 32, DIR_FANIN),
            ("sel",    4, DIR_FANOUT),
            ("cyc",    1, DIR_FANOUT),
            ("stb",    1, DIR_FANOUT),
            ("ack",    1, DIR_FANIN),
            ("we",     1, DIR_FANOUT),
            ("cti",    3, DIR_FANOUT),
            ("bte",    2, DIR_FANOUT),
            ("err",    1, DIR_FANIN)
        ])
        self.sub01 = Interface(addr_width=11,
                             data_width=32,
                             granularity=8,
                             features={"err","cti","bte"},
                             name="sub01")
        self.sub02 = Interface(addr_width=21,
                               data_width=32,
                               granularity=8,
                               features={"err","cti","bte"},
                               name="sub02")
        self.dut = InterconnectShared(
            addr_width=30, data_width=32, granularity=8,
            features={"err","cti","bte"},
            itors=[
                self.master01,
                self.master02
            ],
            targets=[
                (self.sub01, 0),
                (self.sub02, (2**21) << 2)
            ]
        )

    def test_basic(self):
        def sim_test():
            yield self.master01.adr.eq(0)
            yield self.master02.adr.eq(2**21)
            yield self.master01.we.eq(0)
            yield self.master02.we.eq(0)
            #
            for _ in range(5):
                yield self.master01.cyc.eq(1)
                yield self.master02.cyc.eq(1)
                yield
                sub01_cyc = (yield self.sub01.cyc)
                sub02_cyc = (yield self.sub02.cyc)
                if sub01_cyc == 1:
                    yield self.master01.stb.eq(1)
                    yield
                    yield self.sub01.ack.eq(1)
                    yield self.master01.stb.eq(0)
                    yield
                    yield self.sub01.ack.eq(0)
                    yield self.master01.cyc.eq(0)
                elif sub02_cyc == 1:
                    yield self.master02.stb.eq(1)
                    yield
                    yield self.sub02.ack.eq(1)
                    yield self.master02.stb.eq(0)
                    yield
                    yield self.sub02.ack.eq(0)
                    yield self.master02.cyc.eq(0)
                yield

        with Simulator(self.dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()
