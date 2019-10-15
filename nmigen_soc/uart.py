from nmigen import *
from nmigen.lib.cdc import MultiReg
from nmigen_stdio import serial


__all__ = ["RS232RX", "RS232TX"]


class RS232RX(Elaboratable):
    """
    """

    def __init__(self, pins, sys_clk_freq, baudrate, tuning_word=None, data_bits=8, parity="none"):
        self.pins = pins
        self.data = Signal(8)
        self.stb = Signal()
        self.tuning_word = tuning_word
        if self._tuning_word is None:
            self._tuning_word = round(2**32*baudrate/sys_clk_freq)
        self.divisor = 1./(baudrate*sys_clk_freq)
        self._data_bits = data_bits
        self._parity = parity

    def elaborate(self, platform):
        m = Module()

        # Add nmigen_stdio module as submodule
        m.submodules.serial = rx = serial.AsyncSerialRX(
            self.divisor, divisor_bits=None, data_bits=self._data_bits,
            parity=self._parity, pins=self.pins
        )

        uart_clk_rxen = Signal()
        phase_accumulator_rx = Signal(32)

        #
        m.d.comb += [
            self.data.eq(rx.data),
            self.stb.eq(rx.rdy)
        ]

        #
        with m.If(rx.busy):
            m.d.sync += Cat(phase_accumulator_rx, uart_clk_rxen).eq(phase_accumulator_rx + self._tuning_word)
        with m.Else():
            m.d.sync += Cat(phase_accumulator_rx, uart_clk_rxen).eq(2**31)

        return m

    def read(self):
        while not (yield self.stb):
            yield
        value = yield self.data
        # clear stb, otherwise multiple calls to this generator keep returning the same value
        yield
        return value


class RS232TX(Elaboratable):
    """
    """

    def __init__(self, pins, sys_clk_freq, baudrate, tuning_word=None, data_bits=8, parity="none"):
        self.pins = pins
        self.data = Signal(8)
        self.stb = Signal()
        self.ack = Signal()
        self._tuning_word = tuning_word
        if self.tuning_word is None:
            self.tuning_word = round(2**32*baudrate/sys_clk_freq)
        self.divisor = 1./(baudrate*sys_clk_freq)
        self._data_bits = data_bits
        self._parity = parity

    def elaborate(self, platform):
        m = Module()

        # Add nmigen_stdio module as submodule
        m.submodules.serial = tx = serial.AsyncSerialTX(
            self.divisor, divisor_bits=None, data_bits=self._data_bits,
            parity=self._parity, pins=self.pins
        )

        uart_clk_txen = Signal()
        phase_accumulator_tx = Signal(32)

        #
        m.d.comb += [
            tx.data.eq(self.data),
            tx.ack.eq(self.stb),
            self.ack.eq(tx.rdy)
        ]

        #
        with m.If(tx.busy):
            m.d.sync += Cat(phase_accumulator_tx, uart_clk_txen).eq(phase_accumulator_tx + self._tuning_word)
        with m.Else():
            m.d.sync += Cat(phase_accumulator_tx, uart_clk_txen).eq(0)

        return m

    def write(self, data):
        yield self.stb.eq(1)
        yield self.data.eq(data)
        yield
        while not (yield self.ack):
            yield
        yield self.stb.eq(0)


class RS232PHY(Elaboratable):
    """
    """

    def __init__(self, pins, sys_clk_freq, baudrate, **kwargs):
        self.rx = RS232RX(pins, sys_clk_freq, baudrate, **kwargs)
        self.tx = RS232TX(pins, sys_clk_freq, baudrate, **kwargs)

    def elaborate(self, platform):
        m = Module()

        m.submodules.rx = self.rx
        m.submodules.tx = self.tx

        return m
