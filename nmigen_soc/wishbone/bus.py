from enum import Enum
from nmigen import *
from nmigen.hdl.rec import Direction
from nmigen.utils import log2_int

from ..memory import MemoryMap
from ..scheduler import *


__all__ = ["CycleType", "BurstTypeExt", "Interface", "Decoder",
           "Arbiter", "InterconnectShared"]


class CycleType(Enum):
    """Wishbone Registered Feedback cycle type."""
    CLASSIC      = 0b000
    CONST_BURST  = 0b001
    INCR_BURST   = 0b010
    END_OF_BURST = 0b111


class BurstTypeExt(Enum):
    """Wishbone Registered Feedback burst type extension."""
    LINEAR  = 0b00
    WRAP_4  = 0b01
    WRAP_8  = 0b10
    WRAP_16 = 0b11


class Interface(Record):
    """Wishbone interface.

    See the `Wishbone specification <https://opencores.org/howto/wishbone>`_ for description
    of the Wishbone signals. The ``RST_I`` and ``CLK_I`` signals are provided as a part of
    the clock domain that drives the interface.

    Note that the data width of the underlying memory map of the interface is equal to port
    granularity, not port size. If port granularity is less than port size, then the address width
    of the underlying memory map is extended to reflect that.

    Parameters
    ----------
    addr_width : int
        Width of the address signal.
    data_width : int
        Width of the data signals ("port size" in Wishbone terminology).
        One of 8, 16, 32, 64.
    granularity : int
        Granularity of select signals ("port granularity" in Wishbone terminology).
        One of 8, 16, 32, 64.
    features : iter(str)
        Selects the optional signals that will be a part of this interface.
    alignment : int
        Resource and window alignment. See :class:`MemoryMap`.
    name : str
        Name of the underlying record.

    Attributes
    ----------
    The correspondence between the nMigen-SoC signals and the Wishbone signals changes depending
    on whether the interface acts as an initiator or a target.

    adr : Signal(addr_width)
        Corresponds to Wishbone signal ``ADR_O`` (initiator) or ``ADR_I`` (target).
    dat_w : Signal(data_width)
        Corresponds to Wishbone signal ``DAT_O`` (initiator) or ``DAT_I`` (target).
    dat_r : Signal(data_width)
        Corresponds to Wishbone signal ``DAT_I`` (initiator) or ``DAT_O`` (target).
    sel : Signal(data_width // granularity)
        Corresponds to Wishbone signal ``SEL_O`` (initiator) or ``SEL_I`` (target).
    cyc : Signal()
        Corresponds to Wishbone signal ``CYC_O`` (initiator) or ``CYC_I`` (target).
    stb : Signal()
        Corresponds to Wishbone signal ``STB_O`` (initiator) or ``STB_I`` (target).
    we : Signal()
        Corresponds to Wishbone signal ``WE_O``  (initiator) or ``WE_I``  (target).
    ack : Signal()
        Corresponds to Wishbone signal ``ACK_I`` (initiator) or ``ACK_O`` (target).
    err : Signal()
        Optional. Corresponds to Wishbone signal ``ERR_I`` (initiator) or ``ERR_O`` (target).
    rty : Signal()
        Optional. Corresponds to Wishbone signal ``RTY_I`` (initiator) or ``RTY_O`` (target).
    stall : Signal()
        Optional. Corresponds to Wishbone signal ``STALL_I`` (initiator) or ``STALL_O`` (target).
    lock : Signal()
        Optional. Corresponds to Wishbone signal ``LOCK_O`` (initiator) or ``LOCK_I`` (target).
    cti : Signal()
        Optional. Corresponds to Wishbone signal ``CTI_O`` (initiator) or ``CTI_I`` (target).
    bte : Signal()
        Optional. Corresponds to Wishbone signal ``BTE_O`` (initiator) or ``BTE_I`` (target).
    """
    def __init__(self, *, addr_width, data_width, granularity=None, features=frozenset(),
                 alignment=0, name=None):
        if not isinstance(addr_width, int) or addr_width < 0:
            raise ValueError("Address width must be a non-negative integer, not {!r}"
                             .format(addr_width))
        if data_width not in (8, 16, 32, 64):
            raise ValueError("Data width must be one of 8, 16, 32, 64, not {!r}"
                             .format(data_width))
        if granularity is None:
            granularity = data_width
        elif granularity not in (8, 16, 32, 64):
            raise ValueError("Granularity must be one of 8, 16, 32, 64, not {!r}"
                             .format(granularity))
        if granularity > data_width:
            raise ValueError("Granularity {} may not be greater than data width {}"
                             .format(granularity, data_width))
        self.addr_width  = addr_width
        self.data_width  = data_width
        self.granularity = granularity
        granularity_bits = log2_int(data_width // granularity)
        self._alignment = alignment
        self.memory_map  = MemoryMap(addr_width=max(1, addr_width + granularity_bits),
                                     data_width=data_width >> granularity_bits,
                                     alignment=alignment)

        self._features = set(features)
        unknown  = self._features - {"rty", "err", "stall", "lock", "cti", "bte"}
        if unknown:
            raise ValueError("Optional signal(s) {} are not supported"
                             .format(", ".join(map(repr, unknown))))
        layout = [
            ("adr",   addr_width, Direction.FANOUT),
            ("dat_w", data_width, Direction.FANOUT),
            ("dat_r", data_width, Direction.FANIN),
            ("sel",   data_width // granularity, Direction.FANOUT),
            ("cyc",   1, Direction.FANOUT),
            ("stb",   1, Direction.FANOUT),
            ("we",    1, Direction.FANOUT),
            ("ack",   1, Direction.FANIN),
        ]
        if "err" in features:
            layout += [("err", 1, Direction.FANIN)]
        if "rty" in features:
            layout += [("rty", 1, Direction.FANIN)]
        if "stall" in features:
            layout += [("stall", 1, Direction.FANIN)]
        if "lock" in features:
            layout += [("lock",  1, Direction.FANOUT)]
        if "cti" in features:
            layout += [("cti", CycleType,    Direction.FANOUT)]
        if "bte" in features:
            layout += [("bte", BurstTypeExt, Direction.FANOUT)]
        super().__init__(layout, name=name, src_loc_at=1)

    @classmethod
    def from_pure_record(cls, record):
        """Instantiate a :class:`wishbone.Interface` from a simple :class:`Record`
        """
        if not isinstance(record, Record):
            raise TypeError("{!r} is not a Record"
                            .format(record))
        addr_width = len(record.adr)
        if len(record.dat_w) != len(record.dat_r):
            raise AttributeError("Record {!r} has {}-bit long \"dat_w\" "
                                 "but {}-bit long \"dat_r\""
                                 .format(record, len(record.dat_w), len(record.dat_r)))
        data_width = len(record.dat_w)
        if data_width%len(record.sel) != 0:
            raise AttributeError("Record {!r} has invalid granularity value because "
                                 "its data width is {}-bit long but "
                                 "its \"sel\" is {}-bit long"
                                 .format(record, data_width, len(record.sel)))
        granularity = data_width // len(record.sel)
        features = []
        for signal_name in ["rty", "err", "stall", "lock", "cti", "bte"]:
            if hasattr(record, signal_name):
                features.append(signal_name)
        return cls(addr_width=addr_width,
                   data_width=data_width,
                   granularity=granularity,
                   features=features,
                   alignment=0,
                   name=record.name+"_intf")


class Decoder(Elaboratable):
    """Wishbone bus decoder.

    An address decoder for subordinate Wishbone buses.

    Parameters
    ----------
    addr_width : int
        Address width. See :class:`Interface`.
    data_width : int
        Data width. See :class:`Interface`.
    granularity : int
        Granularity. See :class:`Interface`
    features : iter(str)
        Optional signal set. See :class:`Interface`.
    alignment : int
        Window alignment. See :class:`Interface`.

    Attributes
    ----------
    bus : :class:`Interface`
        Bus providing access to subordinate buses.
    """
    def __init__(self, *, addr_width, data_width, granularity=None, features=frozenset(),
                 alignment=0):
        self.bus   = Interface(addr_width=addr_width, data_width=data_width,
                               granularity=granularity, features=features,
                               alignment=alignment)
        self._map  = self.bus.memory_map
        self._subs = dict()

    def align_to(self, alignment):
        """Align the implicit address of the next window.

        See :meth:`MemoryMap.align_to` for details.
        """
        return self._map.align_to(alignment)

    def add(self, sub_bus, *, addr=None, sparse=False):
        """Add a window to a subordinate bus.

        The decoder can perform either sparse or dense address translation. If dense address
        translation is used (the default), the subordinate bus must have the same data width as
        the decoder; the window will be contiguous. If sparse address translation is used,
        the subordinate bus may have data width less than the data width of the decoder;
        the window may be discontiguous. In either case, the granularity of the subordinate bus
        must be equal to or less than the granularity of the decoder.

        See :meth:`MemoryMap.add_resource` for details.
        """
        if not isinstance(sub_bus, Interface):
            raise TypeError("Subordinate bus must be an instance of wishbone.Interface, not {!r}"
                            .format(sub_bus))
        if sub_bus.granularity > self.bus.granularity:
            raise ValueError("Subordinate bus has granularity {}, which is greater than the "
                             "decoder granularity {}"
                             .format(sub_bus.granularity, self.bus.granularity))
        if not sparse:
            if sub_bus.data_width != self.bus.data_width:
                raise ValueError("Subordinate bus has data width {}, which is not the same as "
                                 "decoder data width {} (required for dense address translation)"
                                 .format(sub_bus.data_width, self.bus.data_width))
        else:
            if sub_bus.granularity != sub_bus.data_width:
                raise ValueError("Subordinate bus has data width {}, which is not the same as "
                                 "subordinate bus granularity {} (required for sparse address "
                                 "translation)"
                                 .format(sub_bus.data_width, sub_bus.granularity))
        for opt_output in {"err", "rty", "stall"}:
            if hasattr(sub_bus, opt_output) and not hasattr(self.bus, opt_output):
                raise ValueError("Subordinate bus has optional output {!r}, but the decoder "
                                 "does not have a corresponding input"
                                 .format(opt_output))

        self._subs[sub_bus.memory_map] = sub_bus
        return self._map.add_window(sub_bus.memory_map, addr=addr, sparse=sparse)

    def elaborate(self, platform):
        m = Module()

        ack_fanin   = 0
        err_fanin   = 0
        rty_fanin   = 0
        stall_fanin = 0

        with m.Switch(self.bus.adr):
            for sub_map, (sub_pat, sub_ratio) in self._map.window_patterns():
                sub_bus = self._subs[sub_map]

                m.d.comb += [
                    sub_bus.adr.eq(self.bus.adr << log2_int(sub_ratio)),
                    sub_bus.dat_w.eq(self.bus.dat_w),
                    sub_bus.sel.eq(Cat(Repl(sel, sub_ratio) for sel in self.bus.sel)),
                    sub_bus.we.eq(self.bus.we),
                    sub_bus.stb.eq(self.bus.stb),
                ]
                if hasattr(sub_bus, "lock"):
                    m.d.comb += sub_bus.lock.eq(getattr(self.bus, "lock", 0))
                if hasattr(sub_bus, "cti"):
                    m.d.comb += sub_bus.cti.eq(getattr(self.bus, "cti", CycleType.CLASSIC))
                if hasattr(sub_bus, "bte"):
                    m.d.comb += sub_bus.bte.eq(getattr(self.bus, "bte", BurstTypeExt.LINEAR))

                with m.Case(sub_pat[:-log2_int(self.bus.data_width // self.bus.granularity)]):
                    m.d.comb += [
                        sub_bus.cyc.eq(self.bus.cyc),
                        self.bus.dat_r.eq(sub_bus.dat_r),
                    ]

                ack_fanin |= sub_bus.ack
                if hasattr(sub_bus, "err"):
                    err_fanin |= sub_bus.err
                if hasattr(sub_bus, "rty"):
                    rty_fanin |= sub_bus.rty
                if hasattr(sub_bus, "stall"):
                    stall_fanin |= sub_bus.stall

        m.d.comb += self.bus.ack.eq(ack_fanin)
        if hasattr(self.bus, "err"):
            m.d.comb += self.bus.err.eq(err_fanin)
        if hasattr(self.bus, "rty"):
            m.d.comb += self.bus.rty.eq(rty_fanin)
        if hasattr(self.bus, "stall"):
            m.d.comb += self.bus.stall.eq(stall_fanin)

        return m


class Arbiter(Elaboratable):
    """Wishbone bus arbiter.

    An arbiter for selecting the Wishbone master from several devices.

    Parameters
    ----------
    addr_width : int
        Address width. See :class:`Interface`.
    data_width : int
        Data width. See :class:`Interface`.
    granularity : int
        Granularity. See :class:`Interface`.
    features : iter(str)
        Optional signal set. See :class:`Interface`.
    alignment : int
        Window alignment. See :class:`Interface`.

    Attributes
    ----------
    bus : :class:`Interface`
        Bus providing access to the selected master.
    """
    def __init__(self, *, addr_width, data_width, granularity=None, features=frozenset(),
                 alignment=0, scheduler="rr"):
        self.bus   = Interface(addr_width=addr_width, data_width=data_width,
                               granularity=granularity, features=features,
                               alignment=alignment)
        self._masters = dict()
        if scheduler not in ["rr"]:
            raise ValueError("Scheduling mode must be \"rr\", not {!r}"
                             .format(scheduler))
        self._scheduler = scheduler
        self._next_index = 0

    def add(self, master_bus):
        """Add a device bus to the list of master candidates
        """
        if not isinstance(master_bus, Interface):
            raise TypeError("Master bus must be an instance of wishbone.Interface, not {!r}"
                            .format(master_bus))
        if master_bus.granularity != self.bus.granularity:
            raise ValueError("Master bus has granularity {}, which is not the same as "
                             "arbiter granularity {}"
                             .format(master_bus.granularity, self.bus.granularity))
        if master_bus.data_width != self.bus.data_width:
                raise ValueError("Master bus has data width {}, which is not the same as "
                                 "arbiter data width {})"
                                 .format(master_bus.data_width, self.bus.data_width))
        for opt_output in {"err", "rty", "stall"}:
            if hasattr(master_bus, opt_output) and not hasattr(self.bus, opt_output):
                raise ValueError("Master bus has optional output {!r}, but the arbiter "
                                 "does not have a corresponding input"
                                 .format(opt_output))

        self._masters[master_bus.memory_map] = self._next_index, master_bus
        self._next_index += 1

    def elaborate(self, platform):
        m = Module()

        if self._scheduler == "rr":
            m.submodules.scheduler = scheduler = RoundRobin(self._next_index)
        grant = Signal(self._next_index)
        m.d.comb += [
            # CYC should not be indefinitely asserted. (See RECOMMENDATION 3.05, Wishbone B4)
            scheduler.stb.eq(~self.bus.cyc),
            grant.eq(scheduler.grant)
        ]

        for signal_name, (_, signal_direction) in self.bus.layout.fields.items():
            # FANOUT signals: only mux the granted master with the interface
            if signal_direction == Direction.FANOUT:
                master_signals = Array(getattr(master_bus, signal_name)
                                       for __, (___, master_bus)
                                       in self._masters.items())
                m.d.comb += getattr(self.bus, signal_name).eq(master_signals[grant])
            # FANIN signals: ACK and ERR are ORed to all masters;
            #                all other signals are asserted to the granted master only
            if signal_direction == Direction.FANIN:
                for __, (index, master_bus) in self._masters.items():
                    source = getattr(self.bus, signal_name)
                    dest = getattr(master_bus, signal_name)
                    if signal_name in ["ack", "err"]:
                        m.d.comb += dest.eq(source & (grant == index))
                    else:
                        m.d.comb += dest.eq(source)

        master_requests = [master_bus.cyc & ~master_bus.ack
                           for __, (___, master_bus) in self._masters.items()]
        m.d.comb += scheduler.request.eq(Cat(*master_requests))

        return m


class InterconnectShared(Elaboratable):
    """
    """
    def __init__(self, shared_bus, masters, targets):
        self.addr_width = shared_bus.addr_width
        self.data_width = shared_bus.data_width
        self.granularity = shared_bus.granularity
        self._features = shared_bus._features
        self._alignment = shared_bus._alignment

        self._masters = []
        self._targets = []

        self._masters_convert_stmts = []
        for master_bus in masters:
            if isinstance(master_bus, Interface):
                self._masters.append(master_bus)
            elif isinstance(master_bus, Record):
                master_interface = Interface.from_pure_record(master_bus)
                self._masters_convert_stmts.append(
                    master_bus.connect(master_interface)
                )
                self._masters.append(master_interface)
            else:
                raise TypeError("Master {!r} must be a Wishbone interface"
                                .format(master_bus))

        for target_bus in targets:
            self._targets.append(target_bus)

        self.arbiter = Arbiter(
            addr_width=self.addr_width,
            data_width=self.data_width,
            granularity=self.granularity,
            features=self._features,
            alignment=self._alignment
        )
        for master_bus in self._masters:
            self.arbiter.add(master_bus)

        self.decoder = Decoder(
            addr_width=self.addr_width,
            data_width=self.data_width,
            granularity=self.granularity,
            features=self._features,
            alignment=self._alignment
        )
        for item in self._targets:
            if isinstance(item, Interface):
                self.decoder.add(item)
            elif isinstance(item, tuple) and len(item) == 2:
                self.decoder.add(item[0], addr=item[1])
            else:
                raise TypeError("Target must be a Wishbone interface, "
                                "or a (Wishbone interface, start address) tuple, not {!r}"
                                .format(item))

    def elaborate(self, platform):
        m = Module()

        m.submodules.arbiter = self.arbiter
        m.submodules.decoder = self.decoder

        m.d.comb += (
            self._masters_convert_stmts +
            self.arbiter.bus.connect(self.decoder.bus)
        )

        return m
