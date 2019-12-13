from nmigen import *
from nmigen.lib.cdc import FFSynchronizer
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

        self.cs_n = Pin(1, "oe")        # Note: pins uses ~CS_N
        self.clk  = Pin(1, "oe")
        self.mosi = Pin(1, "oe")
        self.miso = Signal()

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
                                          i_USRMCLKI=self.clk,
                                          i_USRMCLKTS=0)
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
                    with module.If(~jtag_rst_n):
                        module.d.sync += self.jtag.sel.eq(0)
                        module.next = "TLRST"
                with module.State("TLRST"):
                    with module.If(~self.jtag.sel):
                        module.d.sync += self.jtag.sel.eq(jtag_rti1)
                    with module.Else():
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
                FFSynchronizer(self._spi_pins.miso.i, self.miso)
            ]
            m.d.comb += [
                self._spi_pins.wp.eq(0),
                self._spi_pins.hold.eq(0)
            ]
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
            self.jtag.tdo.eq(self.miso),
            # Positive edge: JTAG TAP outputs; SPI device gets input from FPGA
            # Negative edge: JTAG TAP gets input; SPI device outputs to FPGA
            self.clk.o.eq(~self.jtag.tck),
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
        with m.FSM(domain="sys") as fsm:
            with m.State("IDLE"):
                with m.If(self.jtag_sel1_shift & self.jtag.tdi):
                    m.next = "HEAD"
            with m.State("HEAD"):
                m.d.sys += [
                    bits.eq(Cat(self.jtag.tdi, bits)),
                    head.eq(head - 1)
                ]
                with m.If(head == 0):
                    m.next = "XFER"
            with m.State("XFER"):
                m.d.sys += bits.eq(bits - 1)
                with m.If(bits == 0):
                    m.next = "IDLE"
        m.d.comb += [
            self.mosi.o.eq(self.jtag.tdi),
            self.cs_n.o.eq(fsm.ongoing("XFER"))
        ]

        return m
