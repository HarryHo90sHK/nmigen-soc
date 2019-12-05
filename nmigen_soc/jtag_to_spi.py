from nmigen import *
from nmigen.lib.io import Pin


__all__ = ["JTAGtoSPI"]


def _wire_layout():
    return [
        ("sel"     , 1),
        ("shift"   , 1),
        ("capture" , 1),
        ("tck"     , 1),
        ("tdi"     , 1),
        ("tdo"     , 1),
    ]


class JTAGtoSPI(Elaboratable):
    """Note: directly adapted from https://github.com/quartiq/bscan_spi_bitstreams/blob/master/xilinx_bscan_spi.py
    """

    def __init__(self, *, bits=32, device=None, spi_pins=None):
        self._bits = bits

        supported_devices = ["lattice_ecp5"]
        if device is not None and device not in supported_devices:
            raise ValueError("Invalid FPGA device name {!r}; must be one of {}"
                             .format(device, supported_devices))
        self._device = device
        if self._device is not None and spi_pins is None:
            raise ValueError("Pins parameter is missing for this FPGA device {}"
                             .format(self._device))
        self._spi_pins = spi_pins
        self.jtag = Record(_wire_layout())

        self.cs_n = Pin(1, "io")        # Note: pins uses ~CS_N
        self.clk  = Pin(1, "io")
        self.mosi = Pin(1, "io")
        self.miso = Pin(1, "io")

        #
        self.cs_n.o.reset = 1
        self.mosi.o.reset_less = True

        self.jtag_sel1_capture = Signal()   # JTAG chain 1 is selected & in Capture-DR state?
        self.jtag_sel1_shift   = Signal()   # JTAG chain 1 is selected & in Shift-DR state?


    def _add_primitives(self, module):
        """Add submodules as required by certain devices
        """
        # Lattice ECP5:
        if self._device == "lattice_ecp5":
            # Add a USRMCLK module to use a user clock as MCLK
            # "The ECP5 and ECP5-5G devices provide a solution for users 
            # to choose any user clock as MCLK under this scenario 
            # by instantiating USRMCLK macro in your Verilog or VHDL."
            # (see Section 6.1.2 of FPGA-TN-02039-1.7, 
            #  "ECP5 and ECP5-5G sysCONFIG Usage Guide Technical Note")
            module.submodules += Instance("USRMCLK",
                                          i_USRMCLKI=self._spi_pins.clk,
                                          i_USRMCLKTS=self._spi_pins.cs)
            # Add a JTAGG module to expose internal JTAG signals to FPGA
            jtag_sel1_capture_or_shift = Signal()
            jtag_rti1 = Signal()
            jtag_rst_n = Signal()
            module.submodules += Instance("JTAGG",
                                          i_JTDO1=self.jtag.tdo,
                                          o_JTDI=self.jtag.tdi,
                                          o_JTCK=self.jtag.tck,
                                          o_JRTI1=jtag_rti1,
                                          o_JRSTN=jtag_rst_n,
                                          o_JSHIFT=self.jtag.shift,
                                          o_JCE1=jtag_sel1_capture_or_shift)
            # Detect that when chain 1 is selected, whether or not TAP is in Capture-DR or Shift-DR state
            module.d.comb += [
                self.jtag_sel1_capture.eq(jtag_sel1_capture_or_shift & ~self.jtag.shift),
                self.jtag_sel1_shift.eq(jtag_sel1_capture_or_shift & self.jtag.shift)
            ]
            # Detect whether or not chain 1 is selected:
            # Selection happens right after the TRST pin is deasserted, 
            #   i.e. TAP just left Test-Logic-Reset state and is entering Run-Test/Idle state;
            # Thus, when TAP enters RTI state, if JRTI1 is high,
            #   it is implied chain 1 is selected until TAP enters TLR state again
            with module.FSM() as fsm:
                with module.State("IDLE"):
                    with module.If(jtag_rst_n):
                        module.next = "TLRST"
                with module.State("TLRST"):
                    with module.If(~jtag_rst_n):    # Current state = Run-Test/Idle
                        module.d.sync += self.jtag.sel.eq(jtag_rti1)
                        module.next = "IDLE"

        # Other devices:
        else:
            module.d.comb += [
                self.jtag_sel1_capture.eq(self.jtag.sel & self.jtag.capture),
                self.jtag_sel1_shift.eq(self.jtag.sel & self.jtag.shift)
            ]


    def elaborate(self, platform):
        m = Module()

        bits = Signal(self._bits, reset_less=True)
        head = Signal(range(len(bits)), reset=len(bits)-1)
        m.domains.cd_sys = cd_sys = ClockDomain()

        if self._spi_pins is not None:
            self._add_primitives(m)
            m.submodules += [
                platform.get_tristate(self.cs_n, self._spi_pins.cs, None, True),    # Note: cs_n is ~pins.cs
                platform.get_tristate(self.mosi, self._spi_pins.mosi, None, False),
                platform.get_tristate(self.miso, self._spi_pins.miso, None, False),
                platform.get_tristate(self.clk, self._spi_pins.clk, None, False)
            ]
            # Contrain JTAG TCK to 25MHz
            # (see Section 3.32 of FPGA-DS-02012-2.1,
            #  "ECP5 and ECP5-5G Family Data Sheet")
            platform.add_clock_constraint(self.jtag.tck, 25e6)
        # For simulation purpose using no Pins:
        else:
            m.d.comb += [
                self.jtag_sel1_capture.eq(self.jtag.sel & self.jtag.capture),
                self.jtag_sel1_shift.eq(self.jtag.sel & self.jtag.shift)
            ]

        m.d.comb += [
            cd_sys.rst.eq(self.jtag_sel1_capture),
            cd_sys.clk.eq(self.jtag.tck),
            self.cs_n.oe.eq(self.jtag.sel),
            self.clk.oe.eq(self.jtag.sel),
            self.mosi.oe.eq(self.jtag.sel),
            self.miso.oe.eq(0),
            # Do not suppress CLK toggles outside CS_N asserted.
            # Xilinx USRCCLK0 requires three dummy cycles to do anything
            # https://www.xilinx.com/support/answers/52626.html
            # This is fine since CS_N changes only on falling CLK.
            self.clk.o.eq(~self.jtag.tck),
            self.jtag.tdo.eq(self.miso.i),
        ]

        # Latency calculation (in half cycles):
        # 0 (falling TCK, rising CLK):
        #   JTAG adapter: set TDI
        # 1 (rising TCK, falling CLK):
        #   JTAG2SPI: sample TDI -> set MOSI
        #   SPI: set MISO
        # 2 (falling TCK, rising CLK):
        #   SPI: sample MOSI
        #   JTAG2SPI (BSCAN primitive): sample MISO -> set TDO
        # 3 (rising TCK, falling CLK):
        #   JTAG adapter: sample TDO
        with m.FSM() as fsm:
            with m.State("IDLE"):
                with m.If(self.jtag.tdi & self.jtag_sel1_shift):
                    m.next = "HEAD"
            with m.State("HEAD"):
                with m.If(head == 0):
                    m.next = "XFER"
            with m.State("XFER"):
                with m.If(bits == 0):
                    m.next = "IDLE"
        m.d.sync += [
            self.mosi.o.eq(self.jtag.tdi),
            self.cs_n.o.eq(~fsm.ongoing("XFER"))
        ]
        with m.If(fsm.ongoing("HEAD")):
            m.d.sync += [
                bits.eq(Cat(self.jtag.tdi, bits)),
                head.eq(head - 1)
            ]
        with m.If(fsm.ongoing("XFER")):
            m.d.sync += bits.eq(bits - 1)

        return m
