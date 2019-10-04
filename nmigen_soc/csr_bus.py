from nmigen import *

from nmigen_soc.csr import *
from nmigen.hdl.rec import *


__all__ = ["CSRBus"]


class Interface(Record):
    """
    """

    def __init__(self, datwidth, adrwidth):
        Record.__init__(self, [
                ("re"    ,        1 , DIR_FANIN)  ,
                ("we"    ,        1 , DIR_FANIN)  ,
                ("adr"   , adrwidth , DIR_FANIN)  ,
                ("dat_r" , datwidth , DIR_FANOUT) ,
                ("dat_w" , datwidth , DIR_FANIN)
            ])


class CSRBus(Elaboratable):
    """
    """

    def __init__(self, csr, datwidth, adrwidth, baseaddr, addrmask=None, bus=None):
        if not isinstance(csr, CSRGeneric):
            raise TypeError("{!r} is not a CSRGeneric object"
                            .format(csr))
        self.csr = csr
        self.datwidth = datwidth
        self.adrwidth = adrwidth
        self.baseaddr = baseaddr
        self.addrmask = addrmask
        if addrmask is not None:
            self.addrmask = Const(addrmask)
        self.bus = Interface(datwidth, adrwidth) if bus is None else bus

        # Define number of bus-wide signals needed for the data
        self.buscount = (csr.get_size() + datwidth - 1) // datwidth
        # Calculate an address mask if it hasn't been specified
        if addrmask is None:
            self.addrmask = Repl(1, tools.bits_for(self.buscount))
        # Storing data to be read from CSR and written to CSR
        self.r, self.w = (Signal(csr.get_size()) for _ in range(2))
        # Buffer for data to be read from CSR and written to CSR
        self.r_b, self.w_b = (Signal(csr.get_size() - self.datwidth) for _ in range(2))

        # A list of Records representing a stream of outgoing/incoming bytes for reading/writing
        self.minicsrs = [
            Record([
                ("re"  ,               1) ,
                ("dat_r" , self.datwidth) ,
                ("we"  ,               1) ,
                ("dat_w" , self.datwidth)
            ]) for _ in range(self.buscount)
        ]

        # Slice list in the format of: [a.start, a.end+1, b.start, b.end+1, ...]
        self.r_slices = []
        self.w_slices = []

        # Per-field ccessibility check:
        for key, field in csr._fields.items():
            # Find readable bits
            if field.access in (ACCESS_R, ACCESS_R_W):
                self.r_slices.append(field.startbit)
                self.r_slices.append(field.endbit+1)
            # Fine bits that can written for any number of times
            if field.access in (ACCESS_W, ACCESS_R_W):
                self.w_slices.append(field.startbit)
                self.w_slices.append(field.endbit+1)

        # Helper for signal tracing
        self.csr_sig = Signal(csr.get_size())

    def elaborate(self, platform):
        m = Module()

        # Helper for signal tracing
        m.d.comb += self.csr_sig.eq(self.csr.get_signal())

        # A selection signal to determine whether the CSR address range is being accessed
        selected = Signal()
        m.d.comb += selected.eq(self.bus.adr[len(self.addrmask):] == (self.baseaddr >> len(self.addrmask)))
        # Reads: comb for strobes, sync for writing back to the bus
        for i, mc in enumerate(self.minicsrs):
            m.d.comb += mc.re.eq(selected & self.bus.re &
                                ((self.bus.adr & self.addrmask) == i))
        m.d.sync += self.bus.dat_r[:self.datwidth].eq(0)
        with m.If(selected):
            with m.Switch(self.bus.adr & self.addrmask):
                for i, mc in enumerate(self.minicsrs):
                    with m.Case(i):
                        m.d.sync += self.bus.dat_r[:self.datwidth].eq(mc.dat_r)
        # Writes: comb for stobes & reading from the bus
        for i, mc in enumerate(self.minicsrs):
            m.d.comb += [
                mc.we.eq(selected & self.bus.we &
                         ((self.bus.adr & self.addrmask) == i)),
                mc.dat_w.eq(self.bus.dat_w[:self.datwidth])
            ]

        # Data to read
        for ind in range(0,len(self.r_slices),2):
            m.d.comb += [
                self.r[self.r_slices[ind]:self.r_slices[ind+1]]
                    .eq(self.csr[self.r_slices[ind]:self.r_slices[ind+1]])
            ]

        # Data to write
        for ind in range(0,len(self.w_slices),2):
            m.d.comb += [
                self.csr[self.w_slices[ind]:self.w_slices[ind+1]]
                    .eq(self.w[self.w_slices[ind]:self.w_slices[ind+1]])
            ]

        # Finalise data read
        for i, mc in enumerate(self.minicsrs):
            with m.If(mc.re):
                if self.csr.atomic_r:
                    if i == 0:
                        m.d.sync += Cat(mc.dat_r, self.r_b).eq(self.r)
                    else:
                        m.d.sync += mc.dat_r.eq(self.r_b[(i-1)*self.datwidth:i*self.datwidth])
                else:
                    m.d.comb += mc.dat_r.eq(self.r[i*self.datwidth:(i+1)*self.datwidth])

        # Initialise data write
        for i, mc in enumerate(self.minicsrs):
            with m.If(mc.we):
                if self.csr.atomic_w:
                    if i == 0:
                        m.d.sync += self.w.eq(Cat(mc.dat_w, self.w_b))
                    else:
                        m.d.sync += self.w_b[(i-1)*self.datwidth:i*self.datwidth].eq(mc.dat_w)
                else:
                    m.d.comb += self.w[i*self.datwidth:(i+1)*self.datwidth].eq(self.dat_w)

        return m
