from nmigen import *

from nmigen_soc.csr import *


__all__ = ["CSRBus"]


class CSRBus(Elaboratable):
    """
    """

    def __init__(self, csr, buswidth, baseaddr, addrmask=None):
        if not isinstance(csr, CSRGeneric):
            raise TypeError("{!r} is not a CSRGeneric object"
                            .format(csr))
        self.csr = csr
        self.buswidth = buswidth
        self.baseaddr = baseaddr
        if addrmask is not None:
            self.addrmask = addrmask
        # Define number of bus-wide signals needed for the data
        self.buscount = (csr.get_size() + buswidth - 1) // buswidth
        # Calculate an address mask if it hasn't been specified
        if addrmask is None:
            self.addrmask = Repl(1, tools.bits_for(self.buscount))
        # Define upper bound of the address
        self.topaddr = self.baseaddr+self.buscount*self.buswidth
        # Store data to be read from CSR
        self.r = Array([Signal() for _ in range(csr.get_size())])
        # A Signal representing the data bus for reading from CSR
        self.dat_r = Signal(buswidth)
        # Store data to be written to CSR
        self.w = Array([Signal() for _ in range(csr.get_size())])
        # A Signal representing the data bus for writing to CSR
        self.dat_w = Signal(buswidth)
        # Incoming strobe signals for reading/writing (from/to CSR)
        self.re_i, self.we_i = Signal(), Signal()
        # Incoming address signal
        self.adr_i = Signal(self.buswidth)
        # Reset signal and lock signal
        self.rst = Signal(reset=1)
        self.lock = Signal(reset=0)
        # Outgoing acknowledge signal
        self.ack_o = Signal(reset=0)
        # Internal selection signal (which bus-word is being read)
        self.sel = Signal(tools.bits_for(self.buscount))

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

        # Turn off reset
        m.d.sync += self.rst.eq(0)
        # Detect reset signal, unlock then lock again
        with m.If(self.lock & self.rst):
            m.d.sync += self.lock.eq(0)
        with m.Else():
            m.d.sync += self.lock.eq(1)

        # Helper for signal tracing
        m.d.comb += self.csr_sig.eq(self.csr.get_signal())

        # Data to read
        with m.If(self.re_i):
            for ind in range(0,len(self.r_slices),2):
                if self.csr.atomic_r:
                    with m.If(self.ack_o):
                        m.d.sync += [
                            self.ack_o.eq(0),  # Mark something is being read now
                            Cat(self.r[self.r_slices[ind]:self.r_slices[ind+1]])
                                    .eq(self.csr[self.r_slices[ind]:self.r_slices[ind+1]])
                        ]
                else:
                    m.d.comb += [
                        Cat(self.r[self.r_slices[ind]:self.r_slices[ind+1]])
                                .eq(self.csr[self.r_slices[ind]:self.r_slices[ind+1]])
                    ]

        # Communication with external bus
        with m.If((self.adr_i >= self.baseaddr) & (self.adr_i < self.topaddr)):
            # Finalise data read 
            with m.If(self.re_i): 
                for i in range(self.buswidth):
                    if self.csr.atomic_r:
                        with m.If(~self.ack_o):
                            m.d.sync += self.dat_r[i].eq(self.r[(self.adr_i & self.addrmask) + i])
                    else:
                        m.d.sync += self.dat_r[i].eq(self.r[(self.adr_i & self.addrmask) + i])
            # Initiate data write
            with m.Elif(self.we_i & self.ack_o): 
                if self.csr.atomic_w:
                    m.d.sync += self.ack_o.eq(0)    # Mark something is being written now
                for i in range(self.buswidth):
                    m.d.sync += self.w[(self.adr_i & self.addrmask) + i].eq(self.dat_w[i])

        # Data to write for any number of times
        with m.If(self.we_i):
            for ind in range(0,len(self.w_slices),2):
                if self.csr.atomic_w:
                    m.d.sync += [
                        self.csr[self.w_slices[ind]:self.w_slices[ind+1]]
                            .eq(Cat(self.w[self.w_slices[ind]:self.w_slices[ind+1]]))
                    ]
                else:
                    m.d.comb += [
                        self.csr[self.w_slices[ind]:self.w_slices[ind+1]]
                            .eq(Cat(self.w[self.w_slices[ind]:self.w_slices[ind+1]]))
                    ]

        #
        with m.If(~self.re_i & ~self.we_i):
            m.d.sync += self.ack_o.eq(1)

        return m
