from nmigen import *
from nmigen.utils import *

from .bus import Interface


__all__ = ["SRAM"]


class SRAM(Elaboratable):
    """
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
            bus = Interface(addr_width=bits_for(self._memdepth),
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
                m.d.comb += wrport.en[i].eq(self.bus.cyc & self.bus.stb & self.bus.we & self.bus.sel[i])

        # generate ack
        m.d.sync += self.bus.ack.eq(0)
        with m.If(self.bus.cyc & self.bus.stb & ~self.bus.ack):
            m.d.sync += self.bus.ack.eq(1)

        return m