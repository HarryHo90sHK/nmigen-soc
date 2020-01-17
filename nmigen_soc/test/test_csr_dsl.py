import unittest
from nmigen import *
from nmigen.hdl.rec import Layout
from nmigen.back.pysim import *

from ..csr.dsl import *
from ..csr.bus import Element


def debug(*args, enable=False, **kwargs):
    """Helper function for enabling verbose debug messages on testing
    """
    if enable:
        print(*args, **kwargs)

class FieldBuilderTestCase(unittest.TestCase):
    def test_tuples(self):
        with Field("f_enums_tuples", width=10) as f:
            f.e += [
                ("ENUM_A", -0),
                ("ENUM_B", -10),
                ("ENUM_C", 999)
            ]
        self.assertEqual(f.Enums.ENUM_A.value, -0)
        self.assertEqual(f.Enums.ENUM_B.value, -10)
        self.assertEqual(f.Enums.ENUM_C.value, 999)

    def test_ints(self):
        with Field("f_enums_ints", width=2) as f:
            f.e += ["VERY_BAD", "BAD", "GOOD", "VERY_GOOD"]
        self.assertEqual(f.Enums.VERY_BAD.value, 0)
        self.assertEqual(f.Enums.BAD.value, 1)
        self.assertEqual(f.Enums.GOOD.value, 2)
        self.assertEqual(f.Enums.VERY_GOOD.value, 3)

    def test_mixed(self):
        with Field("f_enums_ints", width=8) as f:
            f.enums += [
                "e0", #0
                ("e1", -50), 
                ("e2", -100),
                "e3", #1
                "e4", #2
                ("e5", 50),
                "e6", #51
            ]
        self.assertEqual(f.Enums.e0.value, 0)
        self.assertEqual(f.Enums.e1.value, -50)
        self.assertEqual(f.Enums.e2.value, -100)
        self.assertEqual(f.Enums.e3.value, 1)
        self.assertEqual(f.Enums.e4.value, 2)
        self.assertEqual(f.Enums.e5.value, 50)
        self.assertEqual(f.Enums.e6.value, 51)


class FieldTestCase(unittest.TestCase):
    def test_1_ro(self):
        f = Field("f_1_ro", access="r", 
                  desc="1-bit read-only field")
        # Field attributes
        self.assertEqual(f.name, "f_1_ro")
        self.assertEqual(f.access, Element.Access.R)
        self.assertEqual(f.width, 1)
        self.assertEqual(f.startbit, None)
        self.assertEqual(f.endbit, None)
        self.assertEqual(f.reset_value, 0)
        self.assertEqual(f.desc, "1-bit read-only field")
        # Field internal write strobe
        self.assertEqual(f.int_w_stb.name, "field_f_1_ro_setstb")
        self.assertEqual(f.set_stb.reset, 0)
        self.assertEqual(len(f.set_en), 1)

    def test_8_rw(self):
        f = Field("f_8_rw", access="rw", 
                  width=8, startbit=10, reset_value=255,
                  enums=[("OFF", 0), ("ON", 255)],
                  desc="8-bit read/write field, 2 possible values")
        # Field attributes
        self.assertEqual(f.name, "f_8_rw")
        self.assertEqual(f.access, Element.Access.RW)
        self.assertEqual(f.width, 8)
        self.assertEqual(f.startbit, 10)
        self.assertEqual(f.endbit, 17)
        self.assertEqual(f.reset_value, 255)
        self.assertEqual(f.desc, "8-bit read/write field, 2 possible values")
        # Field internal write strobe
        self.assertEqual(f.int_w_stb.name, "field_f_8_rw_setstb")
        self.assertEqual(f.set_stb.reset, 0)
        self.assertEqual(len(f.set_en), 1)

    def test_10_wo(self):
        f = Field("f_10_wo", access="w", 
                  width=10, startbit=77, reset_value=64,
                  enums=[("MIN", 0), ("MAX", 1023)],
                  desc="10-bit write-only field, 6 possible values")
        with f as field:
            field.enums += [("VERY_LOW", 2**2), ("MODERATELY_LOW", 2**4),
                        ("VERY_HIGH", 2**8), ("MODERATELY_HIGH", 2**6)]
        # Field attributes
        self.assertEqual(f.name, "f_10_wo")
        self.assertEqual(f.access, Element.Access.W)
        self.assertEqual(f.width, 10)
        self.assertEqual(f.startbit, 77)
        self.assertEqual(f.endbit, 86)
        self.assertEqual(f.reset_value, 64)
        self.assertEqual(f.desc, "10-bit write-only field, 6 possible values")
        # Field._enums attributes
        self.assertEqual(f.Enums.MAX.value, 1023)
        self.assertEqual(f.Enums.VERY_HIGH.value, 256)
        self.assertEqual(f.Enums.MODERATELY_HIGH.value, 64)
        self.assertEqual(f.Enums.MODERATELY_LOW.value, 16)
        self.assertEqual(f.Enums.VERY_LOW.value, 4)
        self.assertEqual(f.Enums.MIN.value, 0)
        # Field internal write strobe
        self.assertEqual(f.int_w_stb.name, "field_f_10_wo_setstb")
        self.assertEqual(f.set_stb.reset, 0)
        self.assertEqual(len(f.set_en), 1)

    # TODO: Define some more unit tests about error raising
    #


class RegisterBuilderTestCase(unittest.TestCase):
    def test_flexible_width(self):
        with Register("flexible_width", "rw", 
                      desc="Read-write register with flexible width") as csr:
            csr.fields += [
                Field("r0", access="r"),
                Field("w0", access="w", reset_value=0),
                Field("rw0", reset_value=1)
            ]
        # reg "flexible_width"
        self.assertEqual(len(csr), 3)
        self.assertEqual(csr.name, "flexible_width")
        self.assertEqual(csr.access, Element.Access.RW)
        self.assertEqual(csr.desc, "Read-write register with flexible width")
        # field "rw0", inherited field access
        self.assertEqual(csr.f.rw0.access, Element.Access.RW)
        # field "r0"
        self.assertEqual(csr.f.r0.startbit, 0)
        self.assertEqual(csr.f.r0.width, 1)
        self.assertEqual(csr.f.r0.endbit, 0)
        # field "w0"
        self.assertEqual(csr.f.w0.startbit, 1)
        self.assertEqual(csr.f.w0.width, 1)
        self.assertEqual(csr.f.w0.endbit, 1)
        # field "rw0"
        self.assertEqual(csr.f.rw0.startbit, 2)
        self.assertEqual(csr.f.rw0.width, 1)
        self.assertEqual(csr.f.rw0.endbit, 2)
        # access bitmask
        self.assertEqual(csr._csr._get_access_bitmask("r"), "101")
        self.assertEqual(csr._csr._get_access_bitmask("w"), "110")
        self.assertEqual(csr._csr._get_access_bitmask("rw"), "100")
        # Element & signal name
        self.assertEqual(csr.bus.name, "csr_flexible_width")
        self.assertEqual(csr.signal.name, "csr_flexible_width_signal")
        # Signal properties
        self.assertEqual(csr.signal.reset, 0b100)
        self.assertEqual(len(csr.signal), 3)
        # Register internal write data properties
        self.assertEqual(csr.int_w_data.name, "csr_flexible_width_setval")
        self.assertEqual(csr.set_value.reset, 0)
        self.assertEqual(len(csr.set_val), 3)
        # Register internal write strobe properties
        self.assertEqual(csr.int_w_stb.name, "csr_flexible_width_setstb")
        self.assertEqual(csr.set_enable.reset, 0)
        self.assertEqual(len(csr.set_en), 1)
        # Register slicing (check repr only)
        self.assertEqual(repr(csr[:]), repr(csr._csr[0:3]))
        self.assertEqual(repr(csr[-3]), repr(csr._csr[0]))
        self.assertEqual(repr(csr[1:3]), repr(csr._csr[1:3]))
        # field.signal()
        self.assertEqual(repr(csr.f.r0.s), repr(csr[0:1]))
        self.assertEqual(repr(csr.f.w0.s), repr(csr[1:2]))
        self.assertEqual(repr(csr.f.rw0.s), repr(csr[2:3]))
        # Field slicing (check repr only)
        self.assertEqual(repr(csr.f.w0[:]), repr(csr.f.w0.s[0]))
        self.assertEqual(repr(csr.f.w0[:]), repr(csr[1][0]))
        self.assertEqual(repr(csr.f.r0[0]), repr(csr.f.r0.s[0]))
        self.assertEqual(repr(csr.f.r0[0]), repr(csr[0][0]))
        self.assertEqual(repr(csr.f.rw0[:]), repr(csr.f.rw0.s[0]))
        self.assertEqual(repr(csr.f.rw0[:]), repr(csr[2][0]))
        # field.int_w_data()
        self.assertEqual(repr(csr.f.r0.set_val), repr(csr.int_w_data[0:1]))
        self.assertEqual(repr(csr.f.w0.set_val), repr(csr.int_w_data[1:2]))
        self.assertEqual(repr(csr.f.rw0.set_val), repr(csr.int_w_data[2:3]))
        # Field internal write data slicing (check repr only)
        self.assertEqual(repr(csr.f.rw0.set_value[:]), repr(csr.int_w_data[2][0]))
        self.assertEqual(repr(csr.f.w0.set_value[0]), repr(csr.int_w_data[1][0]))
        self.assertEqual(repr(csr.f.r0.set_value[:]), repr(csr.int_w_data[0][0]))

    def test_fixed_width(self):
        csr = Register("fixed_width", "w", width=20, 
                       fields=[
                           Field("w0", reset_value=1),
                           Field("w1", width=10, startbit=6, reset_value=77),
                           Field("w2", width=2, reset_value=2)
                       ],
                       desc="Write-only register with fixed width")
        # reg "fixed_width"
        self.assertEqual(len(csr), 20)
        self.assertEqual(csr.name, "fixed_width")
        self.assertEqual(csr.access, Element.Access.W)
        self.assertEqual(csr.desc, "Write-only register with fixed width")
        # all fields, inherited field access
        self.assertEqual(csr.f.w0.access, Element.Access.W)
        self.assertEqual(csr.f.w1.access, Element.Access.W)
        self.assertEqual(csr.f.w2.access, Element.Access.W)
        # field "w0"
        self.assertEqual(csr.f.w0.startbit, 0)
        self.assertEqual(csr.f.w0.width, 1)
        self.assertEqual(csr.f.w0.endbit, 0)
        # field "w1"
        self.assertEqual(csr.f.w1.startbit, 6)
        self.assertEqual(csr.f.w1.endbit, 15)
        # field "w2"
        self.assertEqual(csr.f.w2.startbit, 16)
        self.assertEqual(csr.f.w2.endbit, 17)
        # access bitmask
        self.assertEqual(csr._csr._get_access_bitmask("r"), "--000000000000-----0")
        self.assertEqual(csr._csr._get_access_bitmask("w"), "--111111111111-----1")
        self.assertEqual(csr._csr._get_access_bitmask("rw"), "--000000000000-----0")
        # Element & signal name
        self.assertEqual(csr.bus.name, "csr_fixed_width")
        self.assertEqual(csr.signal.name, "csr_fixed_width_signal")
        # Signal properties
        self.assertEqual(csr.signal.reset, 1 | (77<<6) | (2<<16))
        self.assertEqual(len(csr.signal), 20)
        # Register internal write data properties
        self.assertEqual(csr.int_w_data.name, "csr_fixed_width_setval")
        self.assertEqual(csr.set_value.reset, 0)
        self.assertEqual(len(csr.set_val), 20)
        # Register internal write strobe properties
        self.assertEqual(csr.int_w_stb.name, "csr_fixed_width_setstb")
        self.assertEqual(csr.set_enable.reset, 0)
        self.assertEqual(len(csr.set_en), 1)
        # Register slicing (check repr only)
        self.assertEqual(repr(csr[:]), repr(csr._csr[0:20]))
        self.assertEqual(repr(csr[-14]), repr(csr._csr[6]))
        self.assertEqual(repr(csr[-16:-15]), repr(csr._csr[4:5]))
        self.assertEqual(repr(csr[-2:]), repr(csr._csr[18:20]))
        # field.signal()
        self.assertEqual(repr(csr.f.w0.s), repr(csr[0:1]))
        self.assertEqual(repr(csr.f.w1.s), repr(csr[6:16]))
        self.assertEqual(repr(csr.f.w2.s), repr(csr[16:18]))
        # Field slicing (check repr only)
        self.assertEqual(repr(csr.f.w0[:]), repr(csr.f.w0.s[0]))
        self.assertEqual(repr(csr.f.w0[:]), repr(csr[0][0]))
        self.assertEqual(repr(csr.f.w2[-2]), repr(csr.f.w2.s[0]))
        self.assertEqual(repr(csr.f.w2[-2]), repr(csr[16:18][0]))
        self.assertEqual(repr(csr.f.w1[2:-1]), repr(csr.f.w1.s[2:9]))
        self.assertEqual(repr(csr.f.w1[2:-1]), repr(csr[6:16][2:9]))
        # field.int_w_data()
        self.assertEqual(repr(csr.f.w0.int_w_data), repr(csr.set_value[0:1]))
        self.assertEqual(repr(csr.f.w1.int_w_data), repr(csr.set_value[6:16]))
        self.assertEqual(repr(csr.f.w2.int_w_data), repr(csr.set_value[16:18]))
        # Field internal write data slicing (check repr only)
        self.assertEqual(repr(csr.f.w2.int_w_data[-2]), repr(csr.set_val[16:18][0]))
        self.assertEqual(repr(csr.f.w1.int_w_data[2:-1]), repr(csr.set_val[6:16][2:9]))
        self.assertEqual(repr(csr.f.w0.int_w_data[:]), repr(csr.set_val[0][0]))

    # TODO: Define some more unit tests about error raising
    #


class RegisterTestCase(unittest.TestCase):
    def setUp(self):
        with Register("reg_30_rw", "rw", 
                      desc="Read-write register of 30 bit wide") as self.dut:
            self.dut.f += [
                Field("r0", access="r", width=10, reset_value=0x155),
                Field("w0", access="w", width=10, reset_value=0x2aa),
                Field("rw0", width=10, reset_value=0x155)
            ]
        # sync reset
        self.dut_rst = Signal()
        self.dut = ResetInserter(self.dut_rst)(self.dut)

    def test_sim(self):
        def sim_test():
            # read, before write
            yield self.dut.bus.r_stb.eq(1)
            yield
            self.assertEqual((yield self.dut.signal), 0x155aa955)
            self.assertEqual((yield self.dut.bus.r_data), 0x15500155)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 0)
            yield self.dut.bus.r_stb.eq(0)
            # write once
            yield self.dut.bus.w_stb.eq(1)
            yield self.dut.bus.w_data.eq((0x155<<10) | (0x2aa<<20))
            yield
            yield
            self.assertEqual((yield self.dut.signal), 0x2aa55555)
            self.assertEqual((yield self.dut.bus.r_data), 0x00000000)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 0)
            yield self.dut.bus.w_stb.eq(0)
            # read again
            yield self.dut.bus.r_stb.eq(1)
            yield 
            self.assertEqual((yield self.dut.signal), 0x2aa55555)
            self.assertEqual((yield self.dut.bus.r_data), 0x2aa00155)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 0)

        with Simulator(self.dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()

    def test_sim_with_reset(self):
        def sim_test():
            # write once
            yield self.dut.bus.w_stb.eq(1)
            yield self.dut.bus.w_data.eq((0x155<<10) | (0x2aa<<20))
            yield
            yield
            self.assertEqual((yield self.dut.signal), 0x2aa55555)
            self.assertEqual((yield self.dut.bus.r_data), 0x00000000)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 0)
            yield self.dut.bus.w_stb.eq(0)
            # read
            yield self.dut.bus.r_stb.eq(1)
            yield
            self.assertEqual((yield self.dut.signal), 0x2aa55555)
            self.assertEqual((yield self.dut.bus.r_data), 0x2aa00155)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 0)

            # reset and read
            # (sync reset doesn't affect CSR)
            yield self.dut_rst.eq(1)
            yield
            yield self.dut_rst.eq(0)
            yield
            self.assertEqual((yield self.dut.signal), 0x2aa55555)
            self.assertEqual((yield self.dut.bus.r_data), 0x2aa00155)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 0)
            # (Register reset strobe affects CSR)
            yield self.dut.rst_stb.eq(1)
            yield
            yield self.dut.rst_stb.eq(0)
            yield
            self.assertEqual((yield self.dut.signal), 0x155aa955)
            self.assertEqual((yield self.dut.bus.r_data), 0x15500155)
            self.assertEqual((yield self.dut.int_w_stb), 0)
            yield self.dut.bus.r_stb.eq(0)
            # write again
            yield self.dut.bus.w_stb.eq(1)
            yield self.dut.bus.w_data.eq((0x2aa<<10) | (0x2aa<<20))
            yield
            yield
            self.assertEqual((yield self.dut.signal), 0x2aaaa955)
            self.assertEqual((yield self.dut.bus.r_data), 0x00000000)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 0)
            yield self.dut.bus.w_stb.eq(0)
            # read again
            yield self.dut.bus.r_stb.eq(1)
            yield
            self.assertEqual((yield self.dut.signal), 0x2aaaa955)
            self.assertEqual((yield self.dut.bus.r_data), 0x2aa00155)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 0)

        with Simulator(self.dut, vcd_file=open("test_with_reset.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()

    def test_sim_complex(self):
        def sim_test():
            # write once from bus and internal logic simultaneously
            # (priority is given to internal logic)
            yield self.dut.bus.w_stb.eq(1)
            yield self.dut.bus.w_data.eq(0x387 | (0x254<<10) | (0x121<<20))
            yield self.dut.int_w_stb.eq(1)
            yield self.dut.int_w_data.eq(0x121 | (0x387<<10) | (0x254<<20))
            yield
            yield
            self.assertEqual((yield self.dut.signal), 0x254e1d21)
            self.assertEqual((yield self.dut.bus.r_data), 0x00000000)
            self.assertEqual((yield self.dut.rst_stb), 0)
            # read, without deasserting any write strobes
            yield self.dut.bus.r_stb.eq(1)
            yield
            self.assertEqual((yield self.dut.signal), 0x254e1d21)
            self.assertEqual((yield self.dut.bus.r_data), 0x25400121)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 1)
            yield self.dut.bus.r_stb.eq(0)
            # only assert internal write strobe
            yield self.dut.bus.w_stb.eq(0)
            yield self.dut.int_w_stb.eq(1)
            yield
            yield
            self.assertEqual((yield self.dut.signal), 0x254e1d21)
            self.assertEqual((yield self.dut.bus.r_data), 0x00000000)
            self.assertEqual((yield self.dut.rst_stb), 0)
            # read, without deasserting any write strobes
            yield self.dut.bus.r_stb.eq(1)
            yield
            self.assertEqual((yield self.dut.signal), 0x254e1d21)
            self.assertEqual((yield self.dut.bus.r_data), 0x25400121)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 1)
            yield self.dut.bus.r_stb.eq(0)
            # only assert bus write strobe
            yield self.dut.bus.w_stb.eq(1)
            yield self.dut.int_w_stb.eq(0)
            yield
            yield
            self.assertEqual((yield self.dut.signal), 0x12195121)
            self.assertEqual((yield self.dut.bus.r_data), 0x00000000)
            self.assertEqual((yield self.dut.rst_stb), 0)
            # read, without deasserting any write strobes
            yield self.dut.bus.r_stb.eq(1)
            yield
            self.assertEqual((yield self.dut.signal), 0x12195121)
            self.assertEqual((yield self.dut.bus.r_data), 0x12100121)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 0)
            yield self.dut.bus.r_stb.eq(0)
            # only assert internal write strobe of r0 and rw0
            yield self.dut.bus.w_stb.eq(0)
            yield self.dut.int_w_stb.eq(0)
            yield self.dut.f.r0.int_w_stb.eq(1)
            yield self.dut.f.r0.int_w_data.eq(0x266)
            yield self.dut.f.w0.int_w_stb.eq(0)
            yield self.dut.f.rw0.int_w_stb.eq(1)
            yield self.dut.f.rw0.int_w_data.eq(0x242)
            yield
            yield
            self.assertEqual((yield self.dut.signal), 0x24295266)
            self.assertEqual((yield self.dut.bus.r_data), 0x00000000)
            self.assertEqual((yield self.dut.rst_stb), 0)
            # read, without deasserting any write strobes
            yield self.dut.bus.r_stb.eq(1)
            yield
            self.assertEqual((yield self.dut.signal), 0x24295266)
            self.assertEqual((yield self.dut.bus.r_data), 0x24200266)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 0)
            yield self.dut.bus.r_stb.eq(0)
            # deassert internal write strobe of r0 and rw0
            yield self.dut.f.r0.int_w_stb.eq(0)
            yield self.dut.f.rw0.int_w_stb.eq(0)

            # [Reset]
            # sync reset, deasserting all write strobes, and read
            # (sync reset doesn't affect CSR)
            yield self.dut.bus.r_stb.eq(1)
            yield self.dut.bus.w_stb.eq(0)
            yield self.dut.int_w_stb.eq(0)
            yield self.dut_rst.eq(1)
            yield
            yield self.dut_rst.eq(0)
            yield
            self.assertEqual((yield self.dut.signal), 0x24295266)
            self.assertEqual((yield self.dut.bus.r_data), 0x24200266)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 0)
            # CSR reset, with both bus and internal write strobe asserted
            # (priority is given to CSR reset)
            yield self.dut.bus.w_stb.eq(1)
            yield self.dut.int_w_stb.eq(1)
            yield self.dut.rst_stb.eq(1)
            yield
            # Read, deasserting all write strobes
            yield self.dut.bus.w_stb.eq(0)
            yield self.dut.int_w_stb.eq(0)
            yield self.dut.rst_stb.eq(0)
            yield
            self.assertEqual((yield self.dut.signal), 0x155aa955)
            self.assertEqual((yield self.dut.bus.r_data), 0x15500155)
            self.assertEqual((yield self.dut.int_w_stb), 0)
            yield self.dut.bus.r_stb.eq(0)
            # write again, only assert bus write strobe
            yield self.dut.bus.w_stb.eq(1)
            yield self.dut.int_w_stb.eq(0)
            yield self.dut.bus.w_data.eq(0x3bb | (0x3bb<<10) | (0x3bb<<20))
            yield
            yield
            self.assertEqual((yield self.dut.signal), 0x3bbeed55)
            self.assertEqual((yield self.dut.bus.r_data), 0x00000000)
            self.assertEqual((yield self.dut.rst_stb), 0)
            # read again
            yield self.dut.bus.r_stb.eq(1)
            yield
            self.assertEqual((yield self.dut.signal), 0x3bbeed55)
            self.assertEqual((yield self.dut.bus.r_data), 0x3bb00155)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 0)
            yield self.dut.bus.r_stb.eq(0)
            # write again, only assert internal write strobe
            yield self.dut.bus.w_stb.eq(0)
            yield self.dut.int_w_stb.eq(1)
            yield self.dut.int_w_data.eq(0x077 | (0x077<<10) | (0x077<<20))
            yield
            yield
            self.assertEqual((yield self.dut.signal), 0x0771dc77)
            self.assertEqual((yield self.dut.bus.r_data), 0x00000000)
            self.assertEqual((yield self.dut.rst_stb), 0)
            # read again
            yield self.dut.bus.r_stb.eq(1)
            yield
            self.assertEqual((yield self.dut.signal), 0x0771dc77)
            self.assertEqual((yield self.dut.bus.r_data), 0x07700077)
            self.assertEqual((yield self.dut.rst_stb), 0)
            self.assertEqual((yield self.dut.int_w_stb), 1)

        with Simulator(self.dut, vcd_file=open("test_complex.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()


class BankBuilderTestCase(unittest.TestCase):
    def test_basic_mux(self):
        with Bank(name="basic", desc="A basic peripheral",
                  addr_width=13, data_width=10, type="mux") as cbank:
            cbank.r += Register("basic", "rw", 
                                desc="A basic read/write register")
            with cbank.regs.basic:
                cbank.regs.basic.f += [
                    Field("r0", access="r"),
                    Field("w0", access="w"),
                    Field("rw0")
                ]
        # bank "basic"
        self.assertEqual(cbank.name, "basic")
        self.assertEqual(cbank.desc, "A basic peripheral")
        self.assertEqual(cbank.type, "mux")
        # reg "basic"
        self.assertEqual(cbank.r.basic.name, "basic")
        self.assertEqual(cbank.r.basic.access, Element.Access.RW)
        self.assertEqual(cbank.r.basic.desc, "A basic read/write register")
        # Multiplexer attributes
        self.assertEqual(cbank.mux.bus.addr_width, 13)
        self.assertEqual(cbank.mux.bus.data_width, 10)
        # Element & signals names
        self.assertEqual(cbank._elements["basic"].name, "bank_basic_csr_basic")
        self.assertEqual(cbank.registers.basic.signal.name, "bank_basic_csr_basic_signal")
        # Register slicing (check repr only)
        self.assertEqual(repr(cbank.r.basic[:]), repr(cbank._bank._regs["basic"]._csr[:]))
        self.assertEqual(repr(cbank.r.basic[2]), repr(cbank._bank._regs["basic"]._csr[-1]))
        self.assertEqual(repr(cbank.r.basic[0:2]), repr(cbank._bank._regs["basic"]._csr[0:2]))

    def test_nameless_bank_dec(self):
        with Bank(addr_width=6, data_width=14) as cbank:
            cbank.registers += [
                Register("foo", "r", fields=[Field("r0"),
                                             Field("r1"),
                                             Field("r2")]),             # len ==  3
                Register("bar", "w", fields=[Field("w0", width=42)]),   # len == 42
                Register("baz", "rw", fields=[Field("rw0", width=13)],
                         width=15)                                      # len == 15
            ]
        # bank "basic"
        self.assertEqual(cbank.name, None)
        self.assertEqual(cbank.desc, None)
        self.assertEqual(cbank.type, "dec")
        # Decoder attributes
        self.assertEqual(cbank.dec.bus.addr_width, 6)
        self.assertEqual(cbank.dec.bus.data_width, 14)
        # mux for "foo"
        self.assertEqual(cbank._muxes["foo"].bus.addr_width, 1)
        self.assertEqual(cbank._muxes["foo"].bus.data_width, 14)
        # mux for "bar"
        self.assertEqual(cbank._muxes["bar"].bus.addr_width, 2)
        self.assertEqual(cbank._muxes["bar"].bus.data_width, 14)
        # mux for "baz"
        self.assertEqual(cbank._muxes["baz"].bus.addr_width, 1)
        self.assertEqual(cbank._muxes["baz"].bus.data_width, 14)
        # Element names
        self.assertEqual(cbank._elements["foo"].name, "csr_foo")
        self.assertEqual(cbank.registers.foo.signal.name, "csr_foo_signal")
        self.assertEqual(cbank._elements["bar"].name, "csr_bar")
        self.assertEqual(cbank.registers.bar.signal.name, "csr_bar_signal")
        self.assertEqual(cbank._elements["baz"].name, "csr_baz")
        self.assertEqual(cbank.registers.baz.signal.name, "csr_baz_signal")
        # Register slicing (check repr only)
        self.assertEqual(repr(cbank.r.foo[:]), repr(cbank._bank._regs["foo"]._csr[:]))
        self.assertEqual(repr(cbank.r.bar[10:20]), repr(cbank._bank._regs["bar"]._csr[10:20]))
        self.assertEqual(repr(cbank.r.baz[5:12]), repr(cbank._bank._regs["baz"]._csr[5:12]))

    # TODO: Define some more unit tests about error raising
    #


class BankTestCase(unittest.TestCase):
    def test_mux_sim(self, debug_en=False):
        self.dut = Bank(addr_width=5, data_width=8, alignment=2, type="mux")
        self.set_up_registers()
        self.check_mux_alignment()
        self.simulate(type="mux", debug_en=debug_en)

    def debug_mux_sim(self):
        self.test_mux_sim(debug_en=True)

    def test_dec_sim(self, debug_en=False):
        self.dut = Bank(addr_width=5, data_width=8, alignment=2, type="dec")
        self.set_up_registers()
        self.check_dec_alignment()
        self.simulate(type="dec", debug_en=debug_en)

    def debug_dec_sim(self):
        self.test_dec_sim(debug_en=True)

    def set_up_registers(self):
        with self.dut:
            self.dut.r += [
                Register("reg_8_r", "r", width=8, 
                         fields=[Field("val", width=8, reset_value=0x22)]),
                Register("reg_16_rw", "rw", width=16, 
                         fields=[Field("ro", access="r", width=5, reset_value=0x16),
                                 Field("wo", access="w", width=4, reset_value=0x3),
                                 Field("rw", width=7, reset_value=0x4c)]),
                Register("reg_4_w", "w", width=4, 
                         fields=[Field("val", width=4, reset_value=0x4)],
                         alignment=4)
            ]
        self.dut_rst = Signal()
        self.dut = ResetInserter(self.dut_rst)(self.dut)

    def check_mux_alignment(self):
        if not hasattr(self, "dut"):
            return unittest.skip("self.dut has not been instantiated")
        mux = self.dut.mux
        elements = self.dut._elements
        self.assertEqual(list(mux._map.resources()), [
            (elements["reg_8_r"], (0, 1)),
            (elements["reg_16_rw"], (4, 6)),
            (elements["reg_4_w"], (16, 17)),
        ])

    def check_dec_alignment(self):
        if not hasattr(self, "dut"):
            return unittest.skip("self.dut has not been instantiated")
        dec = self.dut.dec
        muxes = self.dut._muxes
        self.assertEqual(list(dec._map.windows()), [
            (muxes["reg_8_r"].bus.memory_map, (0, 2, 1)),
            (muxes["reg_16_rw"].bus.memory_map, (4, 6, 1)),
            (muxes["reg_4_w"].bus.memory_map, (16, 18, 1)),
        ])

    def simulate(self, type, debug_en):
        def get_reg_elem(name):
            return self.dut._elements[name]
        def get_reg_csr_sig(name):
            return self.dut._bank._get_csr(name)[:]
        def concat_chunks(addr_value_dict, addr_lo, addr_hi):
            result = 0
            for addr in range(addr_lo, addr_hi):
                result |= addr_value_dict[addr] << ((addr-addr_lo)*self.dut.data_width)
            return result

        def sim_test():
            # Define "bus" for each type of Bank:
            # - "mux": self.dut.mux.bus
            # - "dec": self.dut.dec.bus
            if type == "mux":
                bus_to_test = self.dut.mux.bus
            elif type == "dec":
                bus_to_test = self.dut.dec.bus

            # Dicts for r_data to assert, w_data to test and w_data to assert
            expected_r_data, actual_w_data, expected_w_data = dict(), dict(), dict()

            # before write, read reg_8_r
            yield bus_to_test.r_stb.eq(1)
            yield bus_to_test.addr.eq(0)
            yield
            self.assertEqual((yield get_reg_elem("reg_8_r").r_stb), 1)
            yield                                               # r_data is latched 1 cycle after r_stb
            self.assertEqual((yield bus_to_test.r_data), 0x22)
            # before write, read reg_16_rw
            expected_r_data[4] = 0x16                           # [8:5] is write-only
            expected_r_data[5] = 0x98                           # The rest can be read
            expected_r_data[6] = 0x00                           # except after addr=5
            expected_r_data[7] = 0x00
            debug("\n[BUS READ reg_16_rw]"
                  "\n<reg_16_rw>", enable=debug_en)
            for addr in range(4, 8):
                yield bus_to_test.addr.eq(addr)
                yield
                debug("addr={}:".format(addr), enable=debug_en)
                debug("\tdec.bus.addr={}, mux.bus.addr={}"
                      .format((yield self.dut.dec.bus.addr) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.addr) if type=="dec" else
                              (yield self.dut.mux.bus.addr)), enable=debug_en)
                debug("\tdec.bus.r_stb={}, mux.bus.r_stb={}, elem.r_stb={}"
                      .format((yield self.dut.dec.bus.r_stb) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.r_stb) if type=="dec" else
                              (yield self.dut.mux.bus.r_stb),
                              (yield get_reg_elem("reg_16_rw").r_stb)), enable=debug_en)
                self.assertEqual((yield get_reg_elem("reg_16_rw").r_stb), 
                                 1 if addr == 4 else 0,
                                 "addr={}".format(addr))        # Only enabled for 1st chunk
                yield                                           # r_data is latched 1 cycle after r_stb
                self.assertEqual((yield bus_to_test.r_data), 
                                 expected_r_data[addr],
                                 "addr={}".format(addr))
            # before write, read reg_4_w [write-only]
            expected_r_data[16] = 0x00                          # Write-only
            expected_r_data[17] = 0x00                          # Write-only
            expected_r_data[18] = 0x00                          # Write-only
            expected_r_data[19] = 0x00                          # Write-only
            for addr in range(16, 20):
                yield bus_to_test.addr.eq(addr)
                yield
                self.assertEqual((yield bus_to_test.r_data), 
                                 expected_r_data[addr],
                                 "addr={}".format(addr))
            yield bus_to_test.r_stb.eq(0)

            # write reg_4_w
            yield bus_to_test.w_stb.eq(1)
            actual_w_data[16], expected_w_data[16] = 0xbb, 0x0b # Only chunk 1 can be written
            actual_w_data[17], expected_w_data[17] = 0xaa, 0x00 # The rest won't be written
            actual_w_data[18], expected_w_data[18] = 0x99, 0x00
            actual_w_data[19], expected_w_data[19] = 0x88, 0x00
            debug("\n[BUS WRITE reg_4_w]"
                  "\n<reg_4_w>", enable=debug_en)
            for addr in range(16, 20):
                yield bus_to_test.addr.eq(addr)
                yield bus_to_test.w_data.eq(actual_w_data[addr])
                yield                                           # w_stb is latched 1 cycle later
                yield
                debug("addr={}:".format(addr), enable=debug_en)
                debug("\tdec.bus.addr={}, mux.bus.addr={}"
                      .format((yield self.dut.dec.bus.addr) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_4_w"].bus.addr) if type=="dec" else
                              (yield self.dut.mux.bus.addr)), enable=debug_en)
                debug("\tdec.bus.w_stb={}, mux.bus.w_stb={}, elem.w_stb={}"
                      .format((yield self.dut.dec.bus.w_stb) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_4_w"].bus.w_stb) if type=="dec" else
                              (yield self.dut.mux.bus.w_stb),
                              (yield get_reg_elem("reg_4_w").w_stb)), enable=debug_en)
                self.assertEqual((yield get_reg_elem("reg_4_w").w_stb), 
                                 1 if addr == 16 else 0,
                                 "addr={}".format(addr))        # Only enabled for last actual chunk
            self.assertEqual((yield get_reg_elem("reg_4_w").w_data),
                             concat_chunks(expected_w_data, 16, 20))
            self.assertEqual((yield get_reg_csr_sig("reg_4_w")), 0xb)
            # write reg_16_rw
            actual_w_data[4], expected_w_data[4] = 0x33, 0x33   # Chunk w_data ignores bitwise access
            actual_w_data[5], expected_w_data[5] = 0x44, 0x44   # Chunks 1-2 can be written
            actual_w_data[6], expected_w_data[6] = 0x55, 0x00   # The rest won't be written
            actual_w_data[7], expected_w_data[7] = 0x66, 0x00
            debug("\n[BUS WRITE reg_16_rw]"
                  "\n<reg_16_rw>", enable=debug_en)
            for addr in range(4, 8):
                yield bus_to_test.addr.eq(addr)
                yield bus_to_test.w_data.eq(actual_w_data[addr])
                yield                                           # w_stb is latched 1 cycle later
                yield
                debug("addr={}:".format(addr), enable=debug_en)
                debug("\tdec.bus.addr={}, mux.bus.addr={}"
                      .format((yield self.dut.dec.bus.addr) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.addr) if type=="dec" else
                              (yield self.dut.mux.bus.addr)), enable=debug_en)
                debug("\tdec.bus.w_stb={}, mux.bus.w_stb={}, elem.w_stb={}"
                      .format((yield self.dut.dec.bus.w_stb) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.w_stb) if type=="dec" else
                              (yield self.dut.mux.bus.w_stb),
                              (yield get_reg_elem("reg_16_rw").w_stb)), enable=debug_en)
                self.assertEqual((yield get_reg_elem("reg_16_rw").w_stb), 
                                 1 if addr == 5 else 0,
                                 "addr={}".format(addr))        # Only enabled for last actual chunk
            self.assertEqual((yield get_reg_elem("reg_16_rw").w_data),
                             concat_chunks(expected_w_data, 4, 8))
            self.assertEqual((yield get_reg_csr_sig("reg_16_rw")), 0x4436)
            # write reg_8_r [read-only]
            yield bus_to_test.addr.eq(0)
            yield bus_to_test.w_data.eq(0xFF)
            yield                                               # w_stb is latched 1 cycle later
            yield
            self.assertEqual((yield get_reg_csr_sig("reg_8_r")), 0x22)
            yield bus_to_test.w_stb.eq(0)

            # after write, read reg_16_rw
            yield bus_to_test.r_stb.eq(1)
            expected_r_data[4] = 0x16                           # [8:5] is write-only
            expected_r_data[5] = 0x44                           # The rest can be read
            expected_r_data[6] = 0x00                           # except after addr=5
            expected_r_data[7] = 0x00
            debug("\n[BUS READ reg_16_rw]"
                  "\n<reg_16_rw>", enable=debug_en)
            for addr in range(4, 8):
                yield bus_to_test.addr.eq(addr)
                yield
                debug("addr={}:".format(addr), enable=debug_en)
                debug("\tdec.bus.addr={}, mux.bus.addr={}"
                      .format((yield self.dut.dec.bus.addr) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.addr) if type=="dec" else
                              (yield self.dut.mux.bus.addr)), enable=debug_en)
                debug("\tdec.bus.r_stb={}, mux.bus.r_stb={}, elem.r_stb={}"
                      .format((yield self.dut.dec.bus.r_stb) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.r_stb) if type=="dec" else
                              (yield self.dut.mux.bus.r_stb),
                              (yield get_reg_elem("reg_16_rw").r_stb)), enable=debug_en)
                self.assertEqual((yield get_reg_elem("reg_16_rw").r_stb), 
                                 1 if addr == 4 else 0,
                                 "addr={}".format(addr))        # Only enabled for 1st chunk
                yield                                           # r_data is latched 1 cycle after r_stb
                self.assertEqual((yield bus_to_test.r_data), 
                                 expected_r_data[addr],
                                 "addr={}".format(addr))

            # sync reset and read
            # (sync reset doesn't affect CSR)
            yield self.dut_rst.eq(1)
            yield
            yield self.dut_rst.eq(0)
            yield
            self.assertEqual((yield get_reg_csr_sig("reg_8_r")), 0x22)
            self.assertEqual((yield get_reg_csr_sig("reg_16_rw")), 0x4436)
            self.assertEqual((yield get_reg_csr_sig("reg_4_w")), 0xb)
            # CSR reset and read
            # (Register reset strobe affects CSR)
            yield self.dut.r.reg_16_rw.rst_stb.eq(1)
            yield
            yield self.dut.r.reg_16_rw.rst_stb.eq(0)
            yield
            self.assertEqual((yield get_reg_csr_sig("reg_8_r")), 0x22)
            self.assertEqual((yield get_reg_csr_sig("reg_16_rw")), 0x9876)
            self.assertEqual((yield get_reg_csr_sig("reg_4_w")), 0xb)
            # Bank reset, with both bus and internal write strobe asserted
            # (priority is given to CSR reset on all registers)
            # - assert bank bus write strobe
            #   (w_stb per element must be driven by bank bus only)
            yield bus_to_test.w_stb.eq(1)
            # - assert all internal write strobes
            #   (int_w_stb per element must be driven individually)
            yield self.dut.r.reg_8_r.int_w_stb.eq(1)
            yield self.dut.r.reg_16_rw.int_w_stb.eq(1)
            yield self.dut.r.reg_4_w.int_w_stb.eq(1)
            # - deassert all per-element reset strobe
            #   (rst_stb per element must be driven individually)
            yield self.dut.r.reg_8_r.rst_stb.eq(0)
            yield self.dut.r.reg_16_rw.rst_stb.eq(0)
            yield self.dut.r.reg_4_w.rst_stb.eq(0)
            # - assert bank bus reset strobe
            #   (rst_stb per element is independent from bank rst_stb)
            yield self.dut.rst_stb.eq(1)
            yield
            # Check register signal, without deasserting bus reset strobe or any write strobes
            self.assertEqual((yield get_reg_csr_sig("reg_8_r")), 0x22)
            self.assertEqual((yield get_reg_csr_sig("reg_16_rw")), 0x9876)
            self.assertEqual((yield get_reg_csr_sig("reg_4_w")), 0xb)
            # read reg_16_rw, deasserting all write strobes but NOT bus reset strobe
            yield bus_to_test.r_stb.eq(1)
            yield bus_to_test.w_stb.eq(0)
            yield self.dut.r.reg_8_r.int_w_stb.eq(0)
            yield self.dut.r.reg_16_rw.int_w_stb.eq(0)
            yield self.dut.r.reg_4_w.int_w_stb.eq(0)
            expected_r_data[4] = 0x16                           # [8:5] is write-only
            expected_r_data[5] = 0x98                           # The rest can be read
            expected_r_data[6] = 0x00                           # except after addr=5
            expected_r_data[7] = 0x00
            debug("\n[BUS READ reg_16_rw, with BANK RESET active]"
                  "\n<reg_16_rw>", enable=debug_en)
            for addr in range(4, 8):
                yield bus_to_test.addr.eq(addr)
                yield
                debug("addr={}:".format(addr), enable=debug_en)
                debug("\tdec.bus.addr={}, mux.bus.addr={}"
                      .format((yield self.dut.dec.bus.addr) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.addr) if type=="dec" else
                              (yield self.dut.mux.bus.addr)), enable=debug_en)
                debug("\tbank.rst_stb={}, csr_obj.bus.rst_stb={}"
                      .format((yield self.dut.rst_stb),
                              (yield self.dut._bank._get_csr("reg_16_rw").rst_stb)), enable=debug_en)
                debug("\tdec.bus.r_stb={}, mux.bus.r_stb={}, elem.r_stb={}"
                      .format((yield self.dut.dec.bus.r_stb) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.r_stb) if type=="dec" else
                              (yield self.dut.mux.bus.r_stb),
                              (yield get_reg_elem("reg_16_rw").r_stb)), enable=debug_en)
                yield                                           # r_data is latched 1 cycle after r_stb
                self.assertEqual((yield bus_to_test.r_data), 
                                 expected_r_data[addr],
                                 "addr={}".format(addr))
            yield bus_to_test.r_stb.eq(0)
            # Deassert bank bus reset strobe now
            yield self.dut.rst_stb.eq(0)
            yield
            # Check register signals again
            self.assertEqual((yield get_reg_csr_sig("reg_8_r")), 0x22)
            self.assertEqual((yield get_reg_csr_sig("reg_16_rw")), 0x9876)
            self.assertEqual((yield get_reg_csr_sig("reg_4_w")), 0x4)

            # write again, with both bus and internal write strobe asserted
            # (priority is given to internal logic per register/field)
            # - assert bank bus write strobe
            yield bus_to_test.w_stb.eq(1)
            # - assert:
            #   - reg_8_r internal write strobe (by register)
            #   - reg_16_rw.wo & reg_16_rw.rw internal write strobes (by field)
            yield self.dut.r.reg_8_r.int_w_stb.eq(1)
            yield self.dut.r.reg_16_rw.int_w_stb.eq(0)
            yield self.dut.r.reg_16_rw.f.ro.int_w_stb.eq(0)
            yield self.dut.r.reg_16_rw.f.wo.int_w_stb.eq(1)
            yield self.dut.r.reg_16_rw.f.rw.int_w_stb.eq(1)
            yield self.dut.r.reg_4_w.int_w_stb.eq(0)
            # - assign reg_8_r internal write data (will be used)
            yield self.dut.r.reg_8_r.int_w_data.eq(0xCC)
            # - assign reg_8_r bus write data (read-only, so w_data won't be used)
            debug("\n[INTERNAL WRITE reg_8_r] & [INTERNAL WRITE reg_16_rw.wo, reg_16_rw.rw] & [BUS WRITE reg_4_w]"
                  "\n<reg_8_r>", enable=debug_en)
            yield bus_to_test.addr.eq(0)
            yield bus_to_test.w_data.eq(0xBB)
            yield                                               # w_stb is latched 1 cycle later
            yield
            debug("addr={}:".format(0), enable=debug_en)
            debug("\tdec.bus.addr={}, mux.bus.addr={}"
                  .format((yield self.dut.dec.bus.addr) if type=="dec" else "--",
                          (yield self.dut._muxes["reg_8_r"].bus.addr) if type=="dec" else
                          (yield self.dut.mux.bus.addr)), enable=debug_en)
            debug("\tcsr_obj.bus.int_w_stb={} (val={})"
                  .format((yield self.dut._bank._get_csr("reg_8_r").int_w_stb),
                          (yield self.dut._bank._get_csr("reg_8_r").f.val.int_w_stb)), enable=debug_en)
            # - assign reg_16_rw internal write data (won't be used)
            yield self.dut.r.reg_16_rw.int_w_data.eq(0xFFFF)
            # - assign reg_16_rw.wo & reg_16_rw.rw internal write data
            yield self.dut.r.reg_16_rw.f.ro.int_w_data.eq(0b10101)          # (won't be used)
            yield self.dut.r.reg_16_rw.f.wo.int_w_data.eq(0b0001)           # (will be used)
            yield self.dut.r.reg_16_rw.f.rw.int_w_data.eq(0b01000011)       # (will be used)
            # - assign reg_16_rw bus write data
            actual_w_data[4], expected_w_data[4] = 0x24, 0x24   # Chunk w_data ignores bitwise access
            actual_w_data[5], expected_w_data[5] = 0x97, 0x97   # Chunks 1-2 can be written
            actual_w_data[6], expected_w_data[6] = 0x68, 0x00   # The rest won't be written
            actual_w_data[7], expected_w_data[7] = 0x53, 0x00
            debug("<reg_16_rw>", enable=debug_en)
            for addr in range(4, 8):
                yield bus_to_test.addr.eq(addr)
                yield bus_to_test.w_data.eq(actual_w_data[addr])
                yield                                           # w_stb is latched 1 cycle later
                yield
                debug("addr={}:".format(addr), enable=debug_en)
                debug("\tdec.bus.addr={}, mux.bus.addr={}"
                      .format((yield self.dut.dec.bus.addr) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.addr) if type=="dec" else
                              (yield self.dut.mux.bus.addr)), enable=debug_en)
                debug("\tcsr_obj.bus.int_w_stb={} (ro={}, wo={}, rw={})"
                      .format((yield self.dut._bank._get_csr("reg_16_rw").int_w_stb),
                              (yield self.dut._bank._get_csr("reg_16_rw").f.ro.int_w_stb),
                              (yield self.dut._bank._get_csr("reg_16_rw").f.wo.int_w_stb),
                              (yield self.dut._bank._get_csr("reg_16_rw").f.rw.int_w_stb)), enable=debug_en)
                debug("\tdec.bus.w_stb={}, mux.bus.w_stb={}, elem.w_stb={}"
                      .format((yield self.dut.dec.bus.w_stb) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.w_stb) if type=="dec" else
                              (yield self.dut.mux.bus.w_stb),
                              (yield get_reg_elem("reg_16_rw").w_stb)), enable=debug_en)
                self.assertEqual((yield get_reg_elem("reg_16_rw").w_stb), 
                                 1 if addr == 5 else 0,
                                 "addr={}".format(addr))        # Only enabled for last actual chunk
            self.assertEqual((yield get_reg_elem("reg_16_rw").w_data),
                             concat_chunks(expected_w_data, 4, 8))
            # - assign reg_4_w bus write data
            actual_w_data[16], expected_w_data[16] = 0x73, 0x03 # Only chunk 1 can be written
            actual_w_data[17], expected_w_data[17] = 0x91, 0x00 # The rest won't be written
            actual_w_data[18], expected_w_data[18] = 0x64, 0x00
            actual_w_data[19], expected_w_data[19] = 0x28, 0x00
            debug("<reg_4_w>", enable=debug_en)
            for addr in range(16, 20):
                yield bus_to_test.addr.eq(addr)
                yield bus_to_test.w_data.eq(actual_w_data[addr])
                yield                                           # w_stb is latched 1 cycle later
                yield
                debug("addr={}:".format(addr), enable=debug_en)
                debug("\tdec.bus.addr={}, mux.bus.addr={}"
                      .format((yield self.dut.dec.bus.addr) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_4_w"].bus.addr) if type=="dec" else
                              (yield self.dut.mux.bus.addr)), enable=debug_en)
                debug("\tcsr_obj.bus.int_w_stb={} (val={})"
                      .format((yield self.dut._bank._get_csr("reg_4_w").int_w_stb),
                              (yield self.dut._bank._get_csr("reg_4_w").f.val.int_w_stb)), enable=debug_en)
                debug("\tdec.bus.w_stb={}, mux.bus.w_stb={}, elem.w_stb={}"
                      .format((yield self.dut.dec.bus.w_stb) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_4_w"].bus.w_stb) if type=="dec" else
                              (yield self.dut.mux.bus.w_stb),
                              (yield get_reg_elem("reg_4_w").w_stb)), enable=debug_en)
                self.assertEqual((yield get_reg_elem("reg_4_w").w_stb), 
                                 1 if addr == 16 else 0,
                                 "addr={}".format(addr))        # Only enabled for last actual chunk
            self.assertEqual((yield get_reg_elem("reg_4_w").w_data),
                             concat_chunks(expected_w_data, 16, 20))
            # - check if register signals prioritise internal write data
            self.assertEqual((yield get_reg_csr_sig("reg_8_r")), 0xCC)      # uses per-reg internal write
            self.assertEqual((yield get_reg_csr_sig("reg_16_rw")), 
                             0b1000011000110110)                            # uses per-field internal write
            self.assertEqual((yield get_reg_csr_sig("reg_4_w")), 0x3)       # uses bus write
            # deassert all write strobes
            yield bus_to_test.w_stb.eq(0)
            yield self.dut.r.reg_8_r.int_w_stb.eq(0)
            yield self.dut.r.reg_16_rw.int_w_stb.eq(0)
            yield self.dut.r.reg_16_rw.f.ro.int_w_stb.eq(0)
            yield self.dut.r.reg_16_rw.f.wo.int_w_stb.eq(0)
            yield self.dut.r.reg_16_rw.f.rw.int_w_stb.eq(0)
            yield self.dut.r.reg_4_w.int_w_stb.eq(0)
            yield self.dut.rst_stb.eq(0)
            # read reg_8_r
            yield bus_to_test.r_stb.eq(1)
            yield bus_to_test.addr.eq(0)
            yield
            self.assertEqual((yield get_reg_elem("reg_8_r").r_stb), 1)
            yield                                               # r_data is latched 1 cycle after r_stb
            self.assertEqual((yield bus_to_test.r_data), 0xCC)
            # read reg_16_rw
            expected_r_data[4] = 0b00010110                     # [8:5] is write-only,  == 0x16
            expected_r_data[5] = 0b10000110                     # The rest can be read, == 0x86
            expected_r_data[6] = 0x00                           # except after addr=5
            expected_r_data[7] = 0x00
            debug("\n[BUS READ reg_16_rw]"
                  "\n<reg_16_rw>", enable=debug_en)
            for addr in range(4, 8):
                yield bus_to_test.addr.eq(addr)
                yield
                debug("addr={}:".format(addr), enable=debug_en)
                debug("\tdec.bus.addr={}, mux.bus.addr={}"
                      .format((yield self.dut.dec.bus.addr) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.addr) if type=="dec" else
                              (yield self.dut.mux.bus.addr)), enable=debug_en)
                debug("\tdec.bus.r_stb={}, mux.bus.r_stb={}, elem.r_stb={}"
                      .format((yield self.dut.dec.bus.r_stb) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.r_stb) if type=="dec" else
                              (yield self.dut.mux.bus.r_stb),
                              (yield get_reg_elem("reg_16_rw").r_stb)), enable=debug_en)
                yield                                           # r_data is latched 1 cycle after r_stb
                self.assertEqual((yield bus_to_test.r_data), 
                                 expected_r_data[addr],
                                 "addr={}".format(addr))
            # Deassert bank bus read strobe now
            yield bus_to_test.r_stb.eq(0)
            yield
            # check final register signals
            self.assertEqual((yield get_reg_csr_sig("reg_8_r")), 0xCC)
            self.assertEqual((yield get_reg_csr_sig("reg_16_rw")), 0x8636)
            self.assertEqual((yield get_reg_csr_sig("reg_4_w")), 0x3)

        with Simulator(self.dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()
