from collections import OrderedDict
from nmigen import *

from nmigen_soc.csr import *
from nmigen.hdl.rec import *


__all__ = ["CSRBus", "CSRBank", "CSRBankArray"]


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


class Interconnect(Elaboratable):
    """
    """

    def __init__(self, master, slaves):
        self.master = master
        self.slaves = slaves

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.master.connect(*self.slaves)
        return m


class CSRBus(Elaboratable):
    """
    """

    def __init__(self, csr, datwidth):
        if not isinstance(csr, CSRGeneric):
            raise TypeError("{!r} is not a CSRGeneric object"
                            .format(csr))
        self.csr = csr
        self.datwidth = datwidth

        # Define number of bus-wide signals needed for the data
        self.buscount = (csr.get_size() + datwidth - 1) // datwidth
        # Storing data to be read from CSR and written to CSR
        self.r = Signal(csr.get_size())
        self.w = Signal(csr.get_size())
        # Buffer for data to be read from CSR and written to CSR
        self.r_b = Signal(csr.get_size() - self.datwidth)
        self.w_b = Signal(csr.get_size() - self.datwidth)

        # A list of Records representing a stream of outgoing/incoming bytes for reading/writing
        self.minicsrs = [
            Record([
                ("re"    ,             1) ,
                ("dat_r" , self.datwidth) ,
                ("we"    ,             1) ,
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


class _CSRBankBuilderRoot:
    """
    """

    def __init__(self, builder):
        self._builder = builder

    def __getattr__(self, name):
        # __getattr__ in superclass is called first
        raise AttributeError("'{}' object has no attribute '{}'"
                             .format(type(self).__name__, name))


class _CSRBankBuilderRegs:
    """
    """

    def __init__(self, builder):
        object.__setattr__(self, "_builder", builder)   # Using "basic" __setattr__()

    def __iadd__(self, csrs):
        for csr in tools.flatten([csrs]):
            self._builder._add_csr_as_bus(csrs)
        # Return itself so that it won't get destroyed
        return self

    def __setattr__(self, name, obj):
        raise AttributeError("Cannot assign attribute '{}'; use '+=' to add a new CSR instead"
                             .format(name))

    def __getattr__(self, name):
        return self._builder._get_csr(name)


class CSRBank(_CSRBankBuilderRoot, Elaboratable):
    """A bank of CSR busses that are auto-generated from a list of CSR objects.
    These busses are contiguous in the address space.
    """

    def __init__(self, name, datwidth, adrwidth, baseaddr, bus=None):
        # TODO: For now, name is required for instantiating a CSRBank.
        #       Later on, it might become implcitly declared, like
        #       using the names of all declared AutoCSR objects in an SoCCore object.
        self.name = name            # TODO: might be removed later on
        self.datwidth = datwidth
        self.adrwidth = adrwidth
        self.baseaddr = baseaddr
        self.bus = Interface(datwidth, adrwidth) if bus is None else bus
        self._busses = OrderedDict()
        self.buscount = 0
        # Define an address mask for the bank
        self.addrmask = 0
        # A CSR bus list representation
        self.csrs = self.c = _CSRBankBuilderRegs(self)

    def _add_csr_as_bus(self, csr):
        if not isinstance(csr, CSRGeneric):
            raise TypeError("{!r} is not a CSRGeneric object"
                            .format(csr))
        if csr.name in self._busses:
            raise NameError("CSR {!r} has a name that is already present in this bank"
                            .format(csr))
        # Add CSR as a new bus in the list
        csrbus = CSRBus(csr, self.datwidth)
        self._busses[csr.name] = csrbus
        self.buscount += csrbus.buscount
        self.addrmask = Repl(1, tools.bits_for(self.buscount))

    def _get_csr(self, name):
        if name in self._busses:
            return self._busses[name].csr
        else:
            raise AttributeError("No CSR named '{}' exists".format(name))

    def elaborate(self, platform):
        m = Module()

        # A selection signal to determine whether the CSR address range is being accessed
        selected = Signal()
        m.d.comb += selected.eq(self.bus.adr[len(self.addrmask):] == (self.baseaddr >> len(self.addrmask)))

        for k, bus in self._busses.items():
            # Reads: comb for strobes, sync for writing back to the bus
            for i, mc in enumerate(bus.minicsrs):
                m.d.comb += mc.re.eq(selected & self.bus.re &
                                    ((self.bus.adr & self.addrmask) == i))
            m.d.sync += self.bus.dat_r[:self.datwidth].eq(0)
            with m.If(selected):
                with m.Switch(self.bus.adr & self.addrmask):
                    for i, mc in enumerate(bus.minicsrs):
                        with m.Case(i):
                            m.d.sync += self.bus.dat_r[:self.datwidth].eq(mc.dat_r)
            # Writes: comb for stobes & reading from the bus
            for i, mc in enumerate(bus.minicsrs):
                m.d.comb += [
                    mc.we.eq(selected & self.bus.we &
                             ((self.bus.adr & self.addrmask) == i)),
                    mc.dat_w.eq(self.bus.dat_w[:self.datwidth])
                ]
            # Add CSRBusses as submodules
            m.submodules += bus

        return m


class CSRBankArray(Elaboratable):
    """[Work In Progress!]
    * should somehow accept a function object `address_map`,
      which can be implemented as `get_csr_dev_address()`
      (but why is it just list_of_csr_devices.index(name)???)
    """

    def __init__(self, src_banks, *interface_args, **interface_kwargs):
        self.src_banks = src_banks
        self.interface_args, self.interface_kwargs = interface_args, interface_kwargs

        self.banks = []
        for bank in self.src_banks:
            csrs = []
            bank.bus = bank_bus = Interface(*self.interface_args, **self.interface_kwargs)
            name, csrs, mapaddr, rmap = (
                bank.name,
                [b.csr for _, b in bank._busses.items()],
                bank.baseaddr,
                bank
            )
            # TODO: A systematic naming method might be needed when generating Rust from nMigen scripts,
            #       i.e. for `get_csr_regions()`
            self.banks.append((name, csrs, mapaddr, rmap))

        # TODO:
        # In misoc, CSRBankArray takes a `source` that contains multiple cores,
        #   in which each "port" is an `AutoCSR`, i.e. can contain bus-independent CSRs,
        #   or bus-independent `Memory` objs.
        # First, if the port has `CSR`s, it calls `get_csrs()` to create a reference to such CSR obj.
        # If the port has `Memory`s, it does the following:
        #   1) Create an SRAM bus that uses the CSRBus interface
        #   2) Create a csr_bus SRAM as a memory-mapping, & add it as a submodule
        #   3) Create a new CSR object by `get_csrs()` of the new SRAM object
        #   4) Add a tuple (name, Memory obj, mapped addr, m-mapping) to `self.srams`
        # Then, for each references to such CSR obj, it does the following:
        #   1) Create a Bank bus that uses the CSRBus interface
        #   2) Create a CSRBank obj as a register-mapping, & add it as a submodule
        #   3) Add a tuple (name, CSR obj, mapped addr, r-mapping) to `self.banks`

    def elaborate(self, platform):
        m = Module()

        # Add the CSRs as submodules
        # TODO: Later on, if this CSRBankArray class doesn't accepts explicitly-instantiated CSRBank objects
        #       while being initialised, the "banks" must hence be instantiated within Array's init,
        #       before being added as submodules.
        for _, __, ___, rmap in self.banks:
            m.submodules += rmap

        return m

    def get_rmaps(self):
        return [rmap for name, csrs, mapaddr, rmap in self.banks]

    def get_mmaps(self):
        # TODO: Might be needed for adding "memories"
        return []

    def get_busses(self):
        return [i.bus for i in self.get_rmaps() + self.get_mmaps()]

