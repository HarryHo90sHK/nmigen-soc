from enum import Enum
from functools import reduce
from operator import or_

from nmigen import *
from nmigen.hdl.rec import *


__all__ = ["Cycle", "Interface", "Arbiter", "Decoder", "InterconnectShared"]


class Cycle(Enum):
    CLASSIC   = 0
    CONSTANT  = 1
    INCREMENT = 2
    END       = 7


def _get_wishbone_layout(data_width, sel_widith):
    return [
        ("adr"   ,         30 , DIR_FANOUT ),
        ("dat_w" , data_width , DIR_FANOUT ),
        ("dat_r" , data_width , DIR_FANIN  ),
        ("sel"   , sel_widith , DIR_FANOUT ),
        ("cyc"   ,          1 , DIR_FANOUT ),
        ("stb"   ,          1 , DIR_FANOUT ),
        ("ack"   ,          1 , DIR_FANIN  ),
        ("we"    ,          1 , DIR_FANOUT ),
        ("cti"   ,          3 , DIR_FANOUT ),
        ("bte"   ,          2 , DIR_FANOUT ),
        ("err"   ,          1 , DIR_FANIN  )
    ]


class Interface(Record):
    def __init__(self, data_width=32):
        Record.__init__(self, 
                        _get_wishbone_layout(data_width,
                                             data_width//8))

    def _do_transaction(self):
        yield self.cyc.eq(1)
        yield self.stb.eq(1)
        yield
        while not (yield self.ack):
            yield
        yield self.cyc.eq(0)
        yield self.stb.eq(0)

    def write(self, adr, dat, sel=None):
        if sel is None:
            sel = 2**len(self.sel) - 1
        yield self.adr.eq(adr)
        yield self.dat_w.eq(dat)
        yield self.sel.eq(sel)
        yield self.we.eq(1)
        yield from self._do_transaction()

    def read(self, adr):
        yield self.adr.eq(adr)
        yield self.we.eq(0)
        yield from self._do_transaction()
        return (yield self.dat_r)


class SRAM(Elaboratable):
    def __init__(self, mem, read_only=False, bus=None):
        self.mem = mem
        self.read_only = read_only
        if bus is None:
            bus = Interface()
        self.bus = bus

    def elaborate(self, platform):
        m = Module()

        if self.mem.width > len(self.bus.dat_r):
            raise NotImplementedError
    
        # read
        m.submodules.rdport = rdport = self.mem.read_port()
        m.d.comb += [
            rdport.addr.eq(self.bus.adr[:len(rdport.addr)]),
            self.bus.dat_r.eq(rdport.data)
        ]

        # write
        if not self.read_only:
            m.submodules.wrport = wrport = self.mem.write_port(granularity=8)
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


class RoundRobin(Elaboratable):
    def __init__(self, n):
        self.n = n
        self.request = Signal(n)
        self.grant = Signal(max=n)

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.grant):
            for i in range(self.n):
                with m.Case(i):
                    with m.If(~self.request[i]):
                        for j in reversed(range(i+1, i+self.n)):
                            t = j % self.n
                            with m.If(self.request[t]):
                                m.d.sync += self.grant.eq(t)
        return m


class Arbiter(Elaboratable):
    def __init__(self, masters, target):
        self.masters = masters
        self.target = target

    def elaborate(self, platform):
        m = Module()

        m.submodules.rr = rr = RoundRobin(len(self.masters))

        # mux master->target signals
        for name, size, direction in wishbone_layout:
            if direction == DIR_FANOUT:
                choices = Array(getattr(m, name) for m in self.masters)
                m.d.comb += getattr(self.target, name).eq(choices[rr.grant])

        # connect target->master signals
        for name, size, direction in wishbone_layout:
            if direction == DIR_FANIN:
                source = getattr(self.target, name)
                for i, master in enumerate(self.masters):
                    dest = getattr(master, name)
                    if name == "ack" or name == "err":
                        m.d.comb += dest.eq(source & (rr.grant == i))
                    else:
                        m.d.comb += dest.eq(source)

        # connect bus requests to round-robin selector
        reqs = [m.cyc & ~m.ack for m in self.masters]
        m.d.comb += rr.request.eq(Cat(*reqs))

        return m


class Decoder(Elaboratable):
    def __init__(self, master, targets, register=False):
        self.master = master
        self.targets = targets
        self.register = register

    def elaborate(self, platform):
        m = Module()

        nt = len(self.targets)
        target_sel = Signal(nt)
        target_sel_r = Signal(nt)

        # decode target addresses
        for i, (fun, bus) in enumerate(self.targets):
            m.d.comb += target_sel[i].eq(fun(self.master.adr))
        if self.register:
            m.d.sync += target_sel_r.eq(target_sel)
        else:
            m.d.comb += target_sel_r.eq(target_sel)

        # connect master->targets signals except cyc
        for target in self.targets:
            for name, size, direction in wishbone_layout:
                if direction == DIR_FANOUT and name != "cyc":
                    m.d.comb += getattr(target[1], name).eq(getattr(self.master, name))

        # combine cyc with target selection signals
        for i, target in enumerate(self.targets):
            m.d.comb += target[1].cyc.eq(self.master.cyc & target_sel[i])

        # generate master ack (resp. err) by ORing all target acks (resp. errs)
        m.d.comb += [
            self.master.ack.eq(reduce(or_, [target[1].ack for target in self.targets])),
            self.master.err.eq(reduce(or_, [target[1].err for target in self.targets]))
        ]

        # mux (1-hot) target data return
        masked = [Repl(target_sel_r[i], len(self.master.dat_r)) & self.targets[i][1].dat_r for i in range(nt)]
        m.d.comb += self.master.dat_r.eq(reduce(or_, masked))

        return m


class InterconnectShared(Module):
    def __init__(self, masters, targets, register=False):
        self.masters = masters
        self.targets = targets
        self.register = register

    def elaborate(self, platform):
        m = Module()
        shared = Interface()
        m.submodules.arbiter = Arbiter(self.masters, shared)
        m.submodules.decoder = Decoder(shared, self.targets, self.register)
        return m
