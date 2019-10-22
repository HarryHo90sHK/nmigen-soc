import unittest
from nmigen import *
from nmigen.hdl.rec import Layout
from nmigen.back.pysim import *

from ..csr.dsl import *


class CSRFieldEnumBuilderTestCase(unittest.TestCase):
    def test_tuples(self):
        f = CSRField("f_enums_tuples", width=10)
        f.e += [
            ("ENUM_A", -0),
            ("ENUM_B", -10),
            ("ENUM_C", 999)
        ]
        self.assertEqual(f.e.ENUM_A, -0)
        self.assertEqual(f.e.ENUM_B, -10)
        self.assertEqual(f.e.ENUM_C, 999)

    def test_ints(self):
        f = CSRField("f_enums_ints", width=2)
        f.e += ["VERY_BAD", "BAD", "GOOD", "VERY_GOOD"]
        self.assertEqual(f.e.VERY_BAD, 0)
        self.assertEqual(f.e.BAD, 1)
        self.assertEqual(f.e.GOOD, 2)
        self.assertEqual(f.e.VERY_GOOD, 3)

    def test_mixed(self):
        f = CSRField("f_enums_ints", width=8)
        f.e += [
            "e0", #0
            ("e1", -50), 
            ("e2", -100),
            "e3", #1
            "e4", #2
            ("e5", 50),
            "e6", #51
        ]
        self.assertEqual(f.e.e0, 0)
        self.assertEqual(f.e.e1, -50)
        self.assertEqual(f.e.e2, -100)
        self.assertEqual(f.e.e3, 1)
        self.assertEqual(f.e.e4, 2)
        self.assertEqual(f.e.e5, 50)
        self.assertEqual(f.e.e6, 51)


class CSRFieldTestCase(unittest.TestCase):
    def test_1_ro(self):
        f = CSRField("f_1_ro", access="r", 
                     desc="1-bit read-only field")
        # CSRField attributes
        self.assertEqual(f.name, "f_1_ro")
        self.assertEqual(f.access, "r")
        self.assertEqual(f.width, 1)
        self.assertEqual(f.startbit, None)
        self.assertEqual(f.endbit, None)
        self.assertEqual(f.reset, 0)
        self.assertEqual(f.desc, "1-bit read-only field")
        # CSRField._signal attributes
        self.assertEqual(f.s.reset, 0)

    def test_8_rw(self):
        f = CSRField("f_8_rw", access="rw", 
                     width=8, startbit=10, reset=255,
                     enums=[("OFF", 0), ("ON", 255)],
                     desc="8-bit read/write field, 2 possible values")
        # CSRField attributes
        self.assertEqual(f.name, "f_8_rw")
        self.assertEqual(f.access, "rw")
        self.assertEqual(f.width, 8)
        self.assertEqual(f.startbit, 10)
        self.assertEqual(f.endbit, 17)
        self.assertEqual(f.reset, 255)
        self.assertEqual(f.desc, "8-bit read/write field, 2 possible values")
        # CSRField._signal attributes
        self.assertEqual(f.s.reset, 255)
        # CSRField._enums attributes
        self.assertEqual(f.e.ON, 255)
        self.assertEqual(f.e.OFF, 0)

    def test_10_wo(self):
        f = CSRField("f_10_wo", access="w", 
                     width=10, startbit=77, reset=64,
                     enums=[("MIN", 0), ("MAX", 1023)],
                     desc="10-bit write-only field, 6 possible values")
        f.e += [("VERY_LOW", 2**2), ("MODERATELY_LOW", 2**4),
                ("VERY_HIGH", 2**8), ("MODERATELY_HIGH", 2**6)]
        # CSRField attributes
        self.assertEqual(f.name, "f_10_wo")
        self.assertEqual(f.access, "w")
        self.assertEqual(f.width, 10)
        self.assertEqual(f.startbit, 77)
        self.assertEqual(f.endbit, 86)
        self.assertEqual(f.reset, 64)
        self.assertEqual(f.desc, "10-bit write-only field, 6 possible values")
        # CSRField._signal attributes
        self.assertEqual(f.s.reset, 64)
        # CSRField._enums attributes
        self.assertEqual(f.e.MAX, 1023)
        self.assertEqual(f.e.VERY_HIGH, 256)
        self.assertEqual(f.e.MODERATELY_HIGH, 64)
        self.assertEqual(f.e.MODERATELY_LOW, 16)
        self.assertEqual(f.e.VERY_LOW, 4)
        self.assertEqual(f.e.MIN, 0)

    # TODO: Define some more unit tests about error raising
    #


class CSRRegisterBuilderTestCase(unittest.TestCase):
    def test_flexible_width(self):
        csr = CSRRegister("flexible_width", "rw", 
                          desc="Read-write register with flexible width")
        with csr as reg:
            reg.f += [
                CSRField("r0", access="r"),
                CSRField("w0", access="w"),
                CSRField("rw0"),
            ]
            # reg "flexible_width"
            self.assertEqual(len(reg), 3)
            self.assertEqual(reg.name, "flexible_width")
            self.assertEqual(reg.access, "rw")
            self.assertEqual(reg.desc, "Read-write register with flexible width")
            # field "rw0", inherited field access
            self.assertEqual(reg.f.rw0.access, "rw")
            # field "r0"
            self.assertEqual(reg.f.r0.startbit, 0)
            self.assertEqual(reg.f.r0.width, 1)
            self.assertEqual(reg.f.r0.endbit, 0)
            # field "w0"
            self.assertEqual(reg.f.w0.startbit, 1)
            self.assertEqual(reg.f.w0.width, 1)
            self.assertEqual(reg.f.w0.endbit, 1)
            # field "rw0"
            self.assertEqual(reg.f.rw0.startbit, 2)
            self.assertEqual(reg.f.rw0.width, 1)
            self.assertEqual(reg.f.rw0.endbit, 2)
            # access bitmask
            self.assertEqual(reg._get_access_bitmask("r"), 0b101)
            self.assertEqual(reg._get_access_bitmask("w"), 0b110)
            self.assertEqual(reg._get_access_bitmask("rw"), 0b100)
        # CSRElement and CSRField._signal names
        self.assertEqual(csr._bus.name, "csr_flexible_width")
        self.assertEqual(csr._reg.f.r0.s.name, "csr_flexible_width__field_r0")
        self.assertEqual(csr._reg.f.w0.s.name, "csr_flexible_width__field_w0")
        self.assertEqual(csr._reg.f.rw0.s.name, "csr_flexible_width__field_rw0")

    def test_fixed_width(self):
        csr = CSRRegister("fixed_width", "w", width=20, 
                          fields=[
                              CSRField("w0"),
                              CSRField("w1", width=10, startbit=6),
                              CSRField("w2", width=2),
                          ],
                          desc="Write-only register with fixed width")
        # reg "flexible_width"
        self.assertEqual(len(csr._reg), 20)
        self.assertEqual(csr._reg.name, "fixed_width")
        self.assertEqual(csr._reg.access, "w")
        self.assertEqual(csr._reg.desc, "Write-only register with fixed width")
        # all fields, inherited field access
        self.assertEqual(csr._reg.f.w0.access, "w")
        self.assertEqual(csr._reg.f.w1.access, "w")
        self.assertEqual(csr._reg.f.w2.access, "w")
        # field "w0"
        self.assertEqual(csr._reg.f.w0.startbit, 0)
        self.assertEqual(csr._reg.f.w0.width, 1)
        self.assertEqual(csr._reg.f.w0.endbit, 0)
        # field "w1"
        self.assertEqual(csr._reg.f.w1.startbit, 6)
        self.assertEqual(csr._reg.f.w1.endbit, 15)
        # field "w2"
        self.assertEqual(csr._reg.f.w2.startbit, 16)
        self.assertEqual(csr._reg.f.w2.endbit, 17)
        # access bitmask
        self.assertEqual(csr._reg._get_access_bitmask("r"), 0b000000000000000000)
        self.assertEqual(csr._reg._get_access_bitmask("w"), 0b111111111111000001)
        self.assertEqual(csr._reg._get_access_bitmask("rw"), 0b000000000000000000)
        # CSRElement and CSRField._signal names
        self.assertEqual(csr._bus.name, "csr_fixed_width")
        self.assertEqual(csr._reg.f.w0.s.name, "csr_fixed_width__field_w0")
        self.assertEqual(csr._reg.f.w1.s.name, "csr_fixed_width__field_w1")
        self.assertEqual(csr._reg.f.w2.s.name, "csr_fixed_width__field_w2")

    # TODO: Define some more unit tests about error raising
    #


class CSRRegisterTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = CSRRegister("reg_30_rw", "rw", 
                               desc="Read-write register of 30 bit wide")
        with self.dut as reg:
            reg.f += [
                CSRField("r0", access="r", width=10, reset=0x155),
                CSRField("w0", access="w", width=10, reset=0x2aa),
                CSRField("rw0", width=10, reset=0x155),
            ]
        self.rst = Signal()
        self.dut = ResetInserter(self.rst)(self.dut)

    def test_sim(self):
        def sim_test():
            # read, before write
            self.assertEqual((yield self.dut._reg[:]), 0x155aa955)
            self.assertEqual((yield self.dut._bus.r_data), 0x15500155)
            # write once
            yield self.dut._bus.w_data.eq((0x155<<10) | (0x2aa<<20))
            yield
            # read, after write
            yield
            self.assertEqual((yield self.dut._reg[:]), 0x2aa55555)
            self.assertEqual((yield self.dut._bus.r_data), 0x2aa00155)
            # reset register
            yield self.rst.eq(1)
            yield
            yield self.rst.eq(0)
            # read, after reset
            yield
            self.assertEqual((yield self.dut._reg[:]), 0x155aa955)
            self.assertEqual((yield self.dut._bus.r_data), 0x15500155)

        _reg_field_sigs = [f._signal for _,f in self.dut._reg._fields.items()]
        with Simulator(self.dut, vcd_file=open("test.vcd", "w"), 
                       gtkw_file=open("test.gtkw", "w"), 
                       traces=[self.dut._bus.r_data,
                               self.dut._bus.w_data, 
                               self.rst,
                               *_reg_field_sigs]) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()
