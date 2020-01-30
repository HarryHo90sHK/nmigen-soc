from nmigen import *
from nmigen.utils import *

from .bus import Interface


__all__ = ["SRAM"]


class SRAM(Elaboratable):
    """SRAM module carrying a volatile memory block (implemented with :class:`Memory`)
    that can be read and write (or only read if the SRAM is read-only) through a Wishbone bus.

    If no Wishbone bus is specified during initialisation, this creates one whose address width
    is just enough to fit the whole memory (i.e. equals to the log2(memory depth) rounded up), and
    whose data width is equal to the memory width.

    Parameters
    ----------
    memory : :class:`Memory`
        The memory to be accessed via the Wishbone bus.
    read_only : bool
        Whether or not the memory is read-only. Defaults to False.
    bus : :class:`Interface` or None
        The Wishbone bus interface providing access to the read/write ports of the memory.
        Optional and defaults to None, which lets this module to instantiate one as described
        above, having the granularity, features and alignment as specified by their
        corresponding parameters.
    granularity : int or None
        If the Wishbone bus is not sepcified, this is the granularity of the Wishbone bus.
        Optional. See :class:`Interface`.
    features : iter(str)
        If the Wishbone bus is not sepcified, this is the optional signal set for the Wishbone bus.
        See :class:`Interface`.

    Attributes
    ----------
    memory : :class:`Memory`
        The memory to be accessed via the Wishbone bus.
    bus : :class:`Interface`
        The Wishbone bus interface providing access to the read/write ports of the memory.
    """
    def __init__(self, memory, read_only=False, bus=None,
                 granularity=None, features=frozenset()):
        if not isinstance(memory, Memory):
            raise TypeError("Memory {!r} is not a Memory"
                            .format(memory))
        self.memory = memory
        self.read_only = read_only
        # Define total address space:
        # - Base: equals memory.depth
        # - Has an additional ReadPort: add rdport.depth
        # - Has an additional WirtePort: add wrport.depth
        self._memdepth = self.memory.depth * 2
        if not read_only:
            self._memdepth += self.memory.depth
        if bus is None:
            bus = Interface(addr_width=max(0, log2_int(self._memdepth, need_pow2=False)),
                            data_width=self.memory.width,
                            granularity=granularity,
                            features=features,
                            alignment=0,
                            name=None)
        self.bus = bus
        self.granularity = bus.granularity

    def elaborate(self, platform):
        m = Module()

        if self.memory.width > len(self.bus.dat_r):
            raise NotImplementedError

        # read
        m.submodules.rdport = rdport = self.memory.read_port()
        m.d.comb += [
            rdport.addr.eq(self.bus.adr[:len(rdport.addr)]),
            self.bus.dat_r.eq(rdport.data)
        ]

        # write
        if not self.read_only:
            m.submodules.wrport = wrport = self.memory.write_port(granularity=self.granularity)
            m.d.comb += [
                wrport.addr.eq(self.bus.adr[:len(rdport.addr)]),
                wrport.data.eq(self.bus.dat_w)
            ]
            for i in range(4):
                m.d.comb += wrport.en[i].eq(self.bus.cyc & self.bus.stb &
                                            self.bus.we & self.bus.sel[i])

        # generate ack
        m.d.sync += self.bus.ack.eq(0)
        with m.If(self.bus.cyc & self.bus.stb & ~self.bus.ack):
            m.d.sync += self.bus.ack.eq(1)

        return m