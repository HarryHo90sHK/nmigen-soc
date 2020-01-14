import unittest
from nmigen import *
from nmigen.hdl.rec import Layout
from nmigen.back.pysim import *

from ..csr.dsl import *
from ..csr.bus import Element


class FieldEnumBuilderTestCase(unittest.TestCase):
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
            f.e += [
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
        # Field.signal attributes
        self.assertEqual(f.s.reset, 0)
        # Field slicing (check repr only)
        self.assertEqual(repr(f[:]), repr(f.s[:]))
        self.assertEqual(repr(f[0]), repr(f.s[0]))

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
        # Field.signal attributes
        self.assertEqual(f.s.reset, 255)
        # Field._enums attributes
        self.assertEqual(f.Enums.ON.value, 255)
        self.assertEqual(f.Enums.OFF.value, 0)
        # Field slicing (check repr only)
        self.assertEqual(repr(f[:]), repr(f.s[:]))
        self.assertEqual(repr(f[-1]), repr(f.s[7]))
        self.assertEqual(repr(f[1:4]), repr(f.s[1:4]))

    def test_10_wo(self):
        f = Field("f_10_wo", access="w", 
                  width=10, startbit=77, reset_value=64,
                  enums=[("MIN", 0), ("MAX", 1023)],
                  desc="10-bit write-only field, 6 possible values")
        with f as field:
            field.e += [("VERY_LOW", 2**2), ("MODERATELY_LOW", 2**4),
                        ("VERY_HIGH", 2**8), ("MODERATELY_HIGH", 2**6)]
        # Field attributes
        self.assertEqual(f.name, "f_10_wo")
        self.assertEqual(f.access, Element.Access.W)
        self.assertEqual(f.width, 10)
        self.assertEqual(f.startbit, 77)
        self.assertEqual(f.endbit, 86)
        self.assertEqual(f.reset_value, 64)
        self.assertEqual(f.desc, "10-bit write-only field, 6 possible values")
        # Field.signal attributes
        self.assertEqual(f.s.reset, 64)
        # Field._enums attributes
        self.assertEqual(f.Enums.MAX.value, 1023)
        self.assertEqual(f.Enums.VERY_HIGH.value, 256)
        self.assertEqual(f.Enums.MODERATELY_HIGH.value, 64)
        self.assertEqual(f.Enums.MODERATELY_LOW.value, 16)
        self.assertEqual(f.Enums.VERY_LOW.value, 4)
        self.assertEqual(f.Enums.MIN.value, 0)
        # Field slicing (check repr only)
        self.assertEqual(repr(f[:]), repr(f.s[:]))
        self.assertEqual(repr(f[9]), repr(f.s[-1]))
        self.assertEqual(repr(f[3:6]), repr(f.s[3:6]))

    # TODO: Define some more unit tests about error raising
    #


class RegisterBuilderTestCase(unittest.TestCase):
    def test_flexible_width(self):
        with Register("flexible_width", "rw", 
                      desc="Read-write register with flexible width") as csr:
            csr.f += [
                Field("r0", access="r"),
                Field("w0", access="w"),
                Field("rw0")
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
        # Element, Field.signal names
        self.assertEqual(csr.bus.name, "csr_flexible_width")
        self.assertEqual(csr.f.r0.s.name, "csr_flexible_width_field_r0")
        self.assertEqual(csr.f.w0.s.name, "csr_flexible_width_field_w0")
        self.assertEqual(csr.f.rw0.s.name, "csr_flexible_width_field_rw0")
        # Register slicing (check repr only)
        self.assertEqual(repr(csr[:]), repr(csr._csr[:]))
        self.assertEqual(repr(csr[:]),
            repr(Cat(csr.f.r0.s[:], csr.f.w0.s[:], csr.f.rw0.s[:]))
        )
        self.assertEqual(repr(csr[-3]), repr(csr._csr[0]))
        self.assertEqual(repr(csr[-3]),
            repr(Cat(csr.f.r0.s[:]))
        )
        self.assertEqual(repr(csr[1:3]), repr(csr._csr[1:3]))
        self.assertEqual(repr(csr[1:3]),
            repr(Cat(csr.f.w0.s[:], csr.f.rw0.s[:]))
        )

    def test_fixed_width(self):
        csr = Register("fixed_width", "w", width=20, 
                       fields=[
                           Field("w0"),
                           Field("w1", width=10, startbit=6),
                           Field("w2", width=2)
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
        # Element, Field.signal names
        self.assertEqual(csr.bus.name, "csr_fixed_width")
        self.assertEqual(csr.f.w0.s.name, "csr_fixed_width_field_w0")
        self.assertEqual(csr.f.w1.s.name, "csr_fixed_width_field_w1")
        self.assertEqual(csr.f.w2.s.name, "csr_fixed_width_field_w2")
        # Register slicing (check repr only)
        self.assertEqual(repr(csr[:]), repr(csr._csr[:]))
        self.assertEqual(repr(csr[:]),
            repr(Cat(csr.f.w0.s[:], csr._csr._dontcare[1:6],
                     csr.f.w1.s[:], csr.f.w2.s[:], csr._csr._dontcare[18:20]))
        )
        self.assertEqual(repr(csr[-14]), repr(csr._csr[6]))
        self.assertEqual(repr(csr[-14]),
            repr(Cat(csr.f.w1.s[:1]))
        )
        self.assertEqual(repr(csr[-16:-15]), repr(csr._csr[4:5]))
        self.assertEqual(repr(csr[-16:-15]),
            repr(Cat(csr._csr._dontcare[4:5]))
        )
        self.assertEqual(repr(csr[5:17]), repr(csr._csr[5:17]))
        self.assertEqual(repr(csr[5:17]),
            repr(Cat(csr._csr._dontcare[5:6], csr.f.w1.s[:], csr.f.w2.s[:1]))
        )

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
            self.assertEqual((yield self.dut._csr[:]), 0x155aa955)
            self.assertEqual((yield self.dut.bus.r_data), 0x15500155)
            yield self.dut.bus.r_stb.eq(0)
            # write once
            yield self.dut.bus.w_stb.eq(1)
            yield self.dut.bus.w_data.eq((0x155<<10) | (0x2aa<<20))
            yield
            yield
            self.assertEqual((yield self.dut._csr[:]), 0x2aa55555)
            self.assertEqual((yield self.dut.bus.r_data), 0x00000000)
            yield self.dut.bus.w_stb.eq(0)
            # read again
            yield self.dut.bus.r_stb.eq(1)
            yield 
            self.assertEqual((yield self.dut._csr[:]), 0x2aa55555)
            self.assertEqual((yield self.dut.bus.r_data), 0x2aa00155)

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
            self.assertEqual((yield self.dut._csr[:]), 0x2aa55555)
            self.assertEqual((yield self.dut.bus.r_data), 0x00000000)
            yield self.dut.bus.w_stb.eq(0)
            # read
            yield self.dut.bus.r_stb.eq(1)
            yield
            self.assertEqual((yield self.dut._csr[:]), 0x2aa55555)
            self.assertEqual((yield self.dut.bus.r_data), 0x2aa00155)

            # reset and read
            # (sync reset doesn't affect CSR)
            yield self.dut_rst.eq(1)
            yield
            yield self.dut_rst.eq(0)
            yield
            self.assertEqual((yield self.dut._csr[:]), 0x2aa55555)
            self.assertEqual((yield self.dut.bus.r_data), 0x2aa00155)
            # (Register reset strobe affects CSR)
            yield self.dut.rststb.eq(1)
            yield
            yield self.dut.rststb.eq(0)
            yield
            self.assertEqual((yield self.dut._csr[:]), 0x155aa955)
            self.assertEqual((yield self.dut.bus.r_data), 0x15500155)
            yield self.dut.bus.r_stb.eq(0)
            # write again
            yield self.dut.bus.w_stb.eq(1)
            yield self.dut.bus.w_data.eq((0x2aa<<10) | (0x2aa<<20))
            yield
            yield
            self.assertEqual((yield self.dut._csr[:]), 0x2aaaa955)
            self.assertEqual((yield self.dut.bus.r_data), 0x00000000)
            yield self.dut.bus.w_stb.eq(0)
            # read again
            yield self.dut.bus.r_stb.eq(1)
            yield
            self.assertEqual((yield self.dut._csr[:]), 0x2aaaa955)
            self.assertEqual((yield self.dut.bus.r_data), 0x2aa00155)

        with Simulator(self.dut, vcd_file=open("test_with_reset.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()


class BankBuilderTestCase(unittest.TestCase):
    def test_basic_mux(self):
        with Bank(name="basic", desc="A basic peripheral",
                  addr_width=13, data_width=10, type="mux") as cbank:
            cbank.r += Register("basic", "rw", 
                                desc="A basic read/write register")
            with cbank.r.basic:
                cbank.r.basic.f += [
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
        # Element, Field.signal names
        self.assertEqual(cbank._elements["basic"].name, "bank_basic_csr_basic")
        self.assertEqual(cbank.r.basic.f.r0.s.name, "bank_basic_csr_basic_field_r0")
        self.assertEqual(cbank.r.basic.f.w0.s.name, "bank_basic_csr_basic_field_w0")
        self.assertEqual(cbank.r.basic.f.rw0.s.name, "bank_basic_csr_basic_field_rw0")
        # Register slicing (check repr only)
        self.assertEqual(repr(cbank.r.basic[:]), repr(cbank._bank._regs["basic"]._csr[:]))
        self.assertEqual(repr(cbank.r.basic[2]), repr(cbank._bank._regs["basic"]._csr[-1]))
        self.assertEqual(repr(cbank.r.basic[0:2]), repr(cbank._bank._regs["basic"]._csr[0:2]))

    def test_nameless_bank_dec(self):
        with Bank(addr_width=6, data_width=14) as cbank:
            cbank.r += [
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
        # Element and Field.signal names
        self.assertEqual(cbank._elements["foo"].name, "csr_foo")
        self.assertEqual(cbank.r.foo.f.r0.s.name, "csr_foo_field_r0")
        self.assertEqual(cbank.r.foo.f.r1.s.name, "csr_foo_field_r1")
        self.assertEqual(cbank.r.foo.f.r2.s.name, "csr_foo_field_r2")
        self.assertEqual(cbank._elements["bar"].name, "csr_bar")
        self.assertEqual(cbank.r.bar.f.w0.s.name, "csr_bar_field_w0")
        self.assertEqual(cbank._elements["baz"].name, "csr_baz")
        self.assertEqual(cbank.r.baz.f.rw0.s.name, "csr_baz_field_rw0")
        # Register slicing (check repr only)
        self.assertEqual(repr(cbank.r.foo[:]), repr(cbank._bank._regs["foo"]._csr[:]))
        self.assertEqual(repr(cbank.r.bar[10:20]), repr(cbank._bank._regs["bar"]._csr[10:20]))
        self.assertEqual(repr(cbank.r.baz[5:12]), repr(cbank._bank._regs["baz"]._csr[5:12]))

    # TODO: Define some more unit tests about error raising
    #


class BankTestCase(unittest.TestCase):
    def test_mux_sim(self):
        self.dut = Bank(addr_width=5, data_width=8, alignment=2, type="mux")
        self.set_up_registers()
        self.check_mux_alignment()
        self.simulate(type="mux")

    def test_dec_sim(self):
        self.dut = Bank(addr_width=5, data_width=8, alignment=2, type="dec")
        self.set_up_registers()
        self.check_dec_alignment()
        self.simulate(type="dec")

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

    def simulate(self, type):
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
            yield                                               # r_data is latched 1 cycle later
            self.assertEqual((yield get_reg_elem("reg_8_r").r_stb), 1)
            yield
            self.assertEqual((yield bus_to_test.r_data), 0x22)
            # before write, read reg_16_rw
            expected_r_data[4] = 0x16                           # [8:5] is write-only
            expected_r_data[5] = 0x98                           # The rest can be read
            expected_r_data[6] = 0x00                           # except after addr=5
            expected_r_data[7] = 0x00
            #print("\nreg_16_rw:")
            for addr in range(4,8):
                yield bus_to_test.addr.eq(addr)
                yield                                           # r_data is latched 1 cycle later
                """
                print("addr={}:".format(addr))
                print("\tdec.bus.addr={}, mux.bus.addr={}"
                      .format((yield self.dut.dec.bus.addr) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.addr) if type=="dec" else
                              (yield self.dut.mux.bus.addr)))
                print("\tdec.bus.r_stb={}, mux.bus.r_stb={}, elem.r_stb={}"
                      .format((yield self.dut.dec.bus.r_stb) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.r_stb) if type=="dec" else
                              (yield self.dut.mux.bus.r_stb),
                              (yield get_reg_elem("reg_16_rw").r_stb)))
                """
                self.assertEqual((yield get_reg_elem("reg_16_rw").r_stb), 
                                 1 if addr == 4 else 0,
                                 "addr={}".format(addr))        # Only enabled for 1st chunk
                yield
                self.assertEqual((yield bus_to_test.r_data), 
                                 expected_r_data[addr],
                                 "addr={}".format(addr))
            # before write, read reg_4_w [write-only]
            expected_r_data[16] = 0x00                          # Write-only
            expected_r_data[17] = 0x00                          # Write-only
            expected_r_data[18] = 0x00                          # Write-only
            expected_r_data[19] = 0x00                          # Write-only
            for addr in range(16,20):
                yield bus_to_test.addr.eq(addr)
                yield                                           # r_data is latched 1 cycle later
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
            #print("\nreg_4_w:")
            for addr in range(16,20):
                yield bus_to_test.addr.eq(addr)
                yield bus_to_test.w_data.eq(actual_w_data[addr])
                yield                                           # w_stb is latched 1 cycle later
                yield
                """
                print("addr={}:".format(addr))
                print("\tdec.bus.addr={}, mux.bus.addr={}"
                      .format((yield self.dut.dec.bus.addr) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_4_w"].bus.addr) if type=="dec" else
                              (yield self.dut.mux.bus.addr)))
                print("\tdec.bus.w_stb={}, mux.bus.w_stb={}, elem.w_stb={}"
                      .format((yield self.dut.dec.bus.w_stb) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_4_w"].bus.w_stb) if type=="dec" else
                              (yield self.dut.mux.bus.w_stb),
                              (yield get_reg_elem("reg_4_w").w_stb)))
                """
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
            #print("\nreg_16_rw:")
            for addr in range(4,8):
                yield bus_to_test.addr.eq(addr)
                yield bus_to_test.w_data.eq(actual_w_data[addr])
                yield                                           # w_stb is latched 1 cycle later
                yield
                """
                print("addr={}:".format(addr))
                print("\tdec.bus.addr={}, mux.bus.addr={}"
                      .format((yield self.dut.dec.bus.addr) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.addr) if type=="dec" else
                              (yield self.dut.mux.bus.addr)))
                print("\tdec.bus.w_stb={}, mux.bus.w_stb={}, elem.w_stb={}"
                      .format((yield self.dut.dec.bus.w_stb) if type=="dec" else "--",
                              (yield self.dut._muxes["reg_16_rw"].bus.w_stb) if type=="dec" else
                              (yield self.dut.mux.bus.w_stb),
                              (yield get_reg_elem("reg_16_rw").w_stb)))
                """
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
            for addr in range(4,8):
                yield bus_to_test.addr.eq(addr)
                yield
                self.assertEqual((yield get_reg_elem("reg_16_rw").r_stb), 
                                 1 if addr == 4 else 0,
                                 "addr={}".format(addr))        # Only enabled for 1st chunk
                yield
                self.assertEqual((yield bus_to_test.r_data), 
                                 expected_r_data[addr],
                                 "addr={}".format(addr))

            # reset register values
            # (sync reset doesn't affect CSR)
            yield self.dut_rst.eq(1)
            yield
            yield self.dut_rst.eq(0)
            yield
            self.assertEqual((yield get_reg_csr_sig("reg_8_r")), 0x22)
            self.assertEqual((yield get_reg_csr_sig("reg_16_rw")), 0x4436)
            self.assertEqual((yield get_reg_csr_sig("reg_4_w")), 0xb)
            # (Register reset strobe affects CSR)
            yield self.dut.r.reg_16_rw.rststb.eq(1)
            yield
            yield self.dut.r.reg_16_rw.rststb.eq(0)
            yield
            self.assertEqual((yield get_reg_csr_sig("reg_8_r")), 0x22)
            self.assertEqual((yield get_reg_csr_sig("reg_16_rw")), 0x9876)
            self.assertEqual((yield get_reg_csr_sig("reg_4_w")), 0xb)
            # (Bank reset strobe affects all CSRs)
            yield self.dut.rststb.eq(1)
            yield
            yield self.dut.rststb.eq(0)
            yield
            self.assertEqual((yield get_reg_csr_sig("reg_8_r")), 0x22)
            self.assertEqual((yield get_reg_csr_sig("reg_16_rw")), 0x9876)
            self.assertEqual((yield get_reg_csr_sig("reg_4_w")), 0x4)
            # after reset, read reg_16_rw
            expected_r_data[4] = 0x16                           # [8:5] is write-only
            expected_r_data[5] = 0x98                           # The rest can be read
            expected_r_data[6] = 0x00                           # except after addr=5
            expected_r_data[7] = 0x00
            for addr in range(4,8):
                yield bus_to_test.addr.eq(addr)
                yield
                yield
                self.assertEqual((yield bus_to_test.r_data), 
                                 expected_r_data[addr],
                                 "addr={}".format(addr))

        with Simulator(self.dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()
