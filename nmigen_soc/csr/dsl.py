from enum import Enum
from collections import OrderedDict
from collections.abc import Iterable

from nmigen import *
from nmigen.hdl.ast import Assign
from nmigen.utils import *
from .bus import *


__all__ = ["Bank", "Register", "Field"]


def _is_bit_overlapping(startbit, endbit, bitrange_list):
    """Helper function for checking if a bit range has overlapped with existing bit ranges
    """
    for bitrange in bitrange_list:
        if max(0, min(endbit, bitrange[1]) - max(startbit, bitrange[0]) + 1) != 0:
            return True
    return False


def _get_rw_bitmasked_logic(r_w, elem_interface, csr_obj):
    """Helper function that returns the statements of assigning to r_data or from w_data,
    based on the bitmask of the csr
    """
    if r_w == "r":
        return [
            elem_interface.r_data[i].eq(csr_obj[i]) for i,v in
            enumerate(format(csr_obj._get_access_bitmask("r"), "b")[::-1]) if v=="1"
        ]
    if r_w == "w":
        return [
            csr_obj[i].eq(elem_interface.w_data[i]) for i,v in
            enumerate(format(csr_obj._get_access_bitmask("w"), "b")[::-1]) if v=="1"
        ]


class _BuilderProxy:
    def __init__(self, builder):
        object.__setattr__(self, "_builder", builder)


class _BuilderAttrReaderProxy:
    """A base class for reading attributes that have been added to a builder.
    """

    def __init__(self, builder, builderattr_name, parent_class, buildee_classes):
        super().__init__()
        object.__setattr__(self, "_dict", dict())
        self._dict["builder"] = builder
        self._dict["builderattr_name"] = builderattr_name
        self._dict["parent_class"] = parent_class
        if not isinstance(buildee_classes, Iterable):
            buildee_classes = [buildee_classes]
        self._dict["buildee_classes"] = buildee_classes

    def __iadd__(self, objs):
        raise AttributeError(("Cannot add attributes; instead, create a context "+
                              "using `with <{}-object> as {}:`, "+
                              "and then add the attributes using `<{}-object>.{} += <{}-object>`")
                             .format(parent_class.__name__, parent_class.__name__.lower(),
                                     parent_class.__name__, builderattr_name,
                                     "/".join([c.__name__ for c in buildee_class])))

    def __setattr__(self, name, value):
        if name in self._dict:
            return self._dict[name]
        raise AttributeError(("Cannot assign attribute '{}'; instead, create a context "+
                              "using `with <{}-object> as {}:`, "+
                              "and then add the attributes using `<{}-object>.{} += <{}-object>`")
                             .format(name,
                                     parent_class.__name__, parent_class.__name__.lower(),
                                     parent_class.__name__, builderattr_name,
                                     "/".join([c.__name__ for c in buildee_class])))

    def __getattr__(self, name):
        if name in object.__getattribute__(self, "_dict"):
            return object.__getattribute__(self, "_dict")[name]
        return self.builder.__getattr__(name)


class Bank(Elaboratable):
    """An elaboratable module to represent a tree of control & status registers. 
    It can be instantiated as one of the following types:

    * A :class:`csr.bus.Multiplexer` object that multiplexes the multiple chunks
      of all registers with just a single bus address signal.
      This type is used with the parameter `type` set to "mux".

    * A :class:`csr.bus.Decoder` object that decodes a bus address to 
      the base address of one of the registers, which is then used to 
      multiple the chunks of just this single register.
      This type is used by default or with the paramter `type` set to "dec".

    Special Notes
    =============

    Do consider the total width of the registers when determining 
    the address width of the bank. Note that when initialising the register,
    the actual width of the register either equals to the `width` parameter value
    if it is specified, or equals to the total width of its fields if otherwise.
    """

    def __init__(self, addr_width, data_width, *args, alignment=0, type="dec", **kwargs):
        self._bank = _BankBuilder(*args, **kwargs)
        self._addr_width = addr_width
        self._data_width = data_width
        self._alignment = alignment
        
        self._type = type
        if self._type == "mux":
            self.mux = self._mux = Multiplexer(addr_width=addr_width,
                                               data_width=data_width)
            self._build_mux_from_bank()
        elif self._type == "dec":
            self.dec = self._dec = Decoder(addr_width=addr_width,
                                           data_width=data_width)
            self._build_dec_from_bank()
        else:
            raise ValueError("Type must be \"mux\" (for multiplexer) or \"dec\" (for decoder), not {!r}"
                             .format(name))

        self._rename_field_sigs()
        # Context manager: 
        # - If outside a `with` block, self.r returns a reader
        # - If inside a `with` block, self.r returns a builder
        self.r_reader = _BuilderAttrReaderProxy(self._bank.r, "r", Bank, Register)
        self.r = self.r_reader

    @property
    def addr_width(self):
        return self._addr_width
    @property
    def data_width(self):
        return self._data_width
    @property
    def alignment(self):
        return self._alignment
    @property
    def type(self):
        return self._type
    @property
    def name(self):
        return self._bank._name
    @property
    def desc(self):
        return self._bank._desc

    def _build_mux_from_bank(self):
        elem_prefix = (
            "bank_" + self._bank.name + "_csr_"
            if self._bank.name is not None
            else "csr_"
        )
        self._elements = dict()
        for csr_name, reg in self._bank._regs.items():
            # Skip if name for this csr already exists in the mux element list
            if csr_name in self._elements:
                continue
            # Otherwise, add the csr
            csr_obj = self._bank._get_csr(csr_name)
            csr_alignment = self._bank._get_alignment(csr_name)
            # Add Element of each csr and change signal names for debugging
            reg.bus.name = elem_prefix + csr_name
            self._elements[csr_name] = reg.bus
            # Set register alignments and add element to mux
            if csr_alignment is not None:
                self._mux.align_to(csr_alignment)
            else:
                self._mux.align_to(self._alignment)
            self._mux.add(reg.bus)

    def _build_dec_from_bank(self):
        elem_prefix = (
            "bank_" + self._bank.name + "_csr_"
            if self._bank.name is not None
            else "csr_"
        )
        self._muxes = dict()
        self._elements = dict()
        for csr_name, reg in self._bank._regs.items():
            # Skip if name for this csr already exists in the mux element list
            if csr_name in self._elements:
                continue
            # Otherwise, add the csr
            csr_obj = self._bank._get_csr(csr_name)
            csr_alignment = self._bank._get_alignment(csr_name)
            # Create Multiplexer for each register
            mux = Multiplexer(addr_width=max(1, log2_int(-(-len(csr_obj)//self._data_width),
                                                         need_pow2=False)),
                              data_width=self._data_width)
            self._muxes[csr_name] = mux
            # Add Element of each csr and change signal names for debugging
            reg.bus.name = elem_prefix + csr_name
            self._elements[csr_name] = reg.bus
            # Add element to the current mux
            mux.add(reg.bus)
            # Set mux alignments and add the mux bus to the decoder
            if csr_alignment is not None:
                self._dec.align_to(csr_alignment)
            else:
                self._dec.align_to(self._alignment)
            self._dec.add(mux.bus)

    def _rename_field_sigs(self):
        """Change names of field signals and their reset signals for debugging
        """
        elem_prefix = (
            "bank_" + self._bank.name + "_"
            if self._bank.name is not None
            else ""
        )
        for csr_name in self._bank._regs:
            csr_obj = self._bank._get_csr(csr_name)
            for field_name, field in csr_obj._fields.items():
                field.signal.name = elem_prefix + field.signal.name
                field.reset_strobe.name = elem_prefix + field.reset_strobe.name

    def __enter__(self):
        self.r = self._bank.r
        return self

    def __exit__(self, e_type, e_value, e_tb):
        self.r = self.r_reader

        if self._type == "mux":
            self._build_mux_from_bank()
        elif self._type == "dec":
            self._build_dec_from_bank()

        self._rename_field_sigs()

    def elaborate(self, platform):
        """Elaborate
        """
        m = Module()

        if self._type == "mux":
            m.submodules.mux = self._mux
        elif self._type == "dec":
            m.submodules.dec = self._dec
            for _, mux in self._muxes.items():
                m.submodules += mux

        for csr_name, elem in self._elements.items():
            csr_obj = self._bank._get_csr(csr_name)
            # Read logic
            if elem.access.readable():
                with m.If(elem.r_stb):
                    m.d.comb += _get_rw_bitmasked_logic("r", elem, csr_obj)
                with m.Else():
                    m.d.comb += elem.r_data.eq(0)
            # Write logic
            if elem.access.writable():
                reset_val = 0
                for _, field in csr_obj._fields.items():
                    reset_val |= (field._reset_value << field._startbit)
                csr_sig = Signal(len(csr_obj), reset=reset_val)
                m.d.sync += csr_sig.eq(csr_obj[:])
                with m.If(elem.w_stb):
                    m.d.comb += _get_rw_bitmasked_logic("w", elem, csr_obj)
                with m.Else():
                    m.d.comb += csr_obj[:].eq(csr_sig)
            # Reset logic
            for _, field in csr_obj._fields.items():
                reset_now = Signal(reset=0, name=field.signal.name+"_rstnow")
                with m.If(field.reset_strobe):
                    m.d.sync += [
                        field.reset_strobe.eq(0),
                        reset_now.eq(1)
                    ]
                with m.If(reset_now):
                    m.d.comb += field.signal.eq(field.reset_value)
                    m.d.sync += reset_now.eq(0)
        return m


class _BankBuilderRegs(_BuilderProxy):
    def __iadd__(self, regs):
        if not isinstance(regs, Iterable):
            regs = [regs]
        for reg in regs:
            self._builder._add_reg(reg)
        return self

    def __setattr__(self, name, obj):
        raise AttributeError("Cannot assign attribute '{}'; use '+=' to add a new register instead"
                             .format(name))

    def __getattr__(self, name):
        """Returns the register that is referenced by the queried name.
        """
        return self._builder._get_reg(name)


class _BankBuilder:
    """A bank representation for control & status registers.

    Parameters
    ----------
    name : str or None
        Name of the register bank. Optional.
    desc : str or None
        Description of the register bank. Optional.
    """

    def __init__(self, *, name=None, desc=None):
        if name is not None and not isinstance(name, str):
            raise TypeError("Name must be a string, not {!r}"
                            .format(name))
        self._name = name
        if desc is not None and not isinstance(desc, str):
            raise TypeError("Description must be a string, not {!r}"
                            .format(desc))
        self._desc = desc
        self._regs = OrderedDict()
        # A CSR register list representation
        self.registers = self.regs = self.r = _BankBuilderRegs(self)

    @property
    def name(self):
        return self._name
    @property
    def desc(self):
        return self._desc

    def _add_reg(self, reg):
        """Converts reg to _RegisterInBank,
        and adds reg to bank._regs.
        """
        if not isinstance(reg, _RegisterBase):
            raise TypeError("{!r} is not an object created within a with block for Bank, or using Register()"
                            .format(reg))
        if reg._csr.name in self._regs:
            raise NameError("Register {!r} has a name that is already present in this bank"
                            .format(reg))
        # Add CSR to list
        self._regs[reg._csr.name] = reg
        # Change reg to non-Elaboratable
        reg.__class__ = _RegisterInBank

    def _get_reg(self, name):
        """Returns reg
        """
        if name in self._regs:
            return self._regs[name]
        else:
            raise AttributeError("No register named '{}' exists".format(name))

    def _get_csr(self, name):
        """Returns reg._csr
        """
        if name in self._regs:
            return self._regs[name]._csr
        else:
            raise AttributeError("No register named '{}' exists".format(name))

    def _get_alignment(self, name):
        """Returns reg.alignment
        """
        if name in self._regs:
            return self._regs[name].alignment
        else:
            raise AttributeError("No register named '{}' exists".format(name))

    def __repr__(self):
        return "(csrbank {})".format(self._name)


class Register:
    """An 'abstract' class that can be initialised as any one of the following classes:

    * :class:`_RegisterInBank`, a normal class,
      if this object is created within a `with` block for :class:`Bank`,
      or created explicity with `standalone=False`.

    * :class:`_RegisterStandalone`, an :class:`Elaboratable`,
      if otherwise.
    """
    def __new__(cls, *args, standalone=True, **kwargs):
        kwargs["standalone"] = standalone
        newcls = _RegisterStandalone if standalone else _RegisterInBank
        self = newcls.__new__(newcls, *args, **kwargs)
        newcls.__init__(self, *args, **kwargs)
        return self


class _RegisterBase:
    """
    """

    def __init__(self, *args, standalone=None, alignment=None, **kwargs):
        super().__init__()
        self._csr = _RegisterBuilder(*args, **kwargs)
        self.f = _BuilderAttrReaderProxy(self._csr.f, "f", Register, Field)
        self._alignment = alignment
        # Context manager: 
        # - If outside a `with` block, self.r returns a reader
        # - If inside a `with` block, self.r returns a builder
        self.f_reader = _BuilderAttrReaderProxy(self._csr.f, "f", Register, Field)
        self.f = self.f_reader

    @property
    def alignment(self):
        return self._alignment
    # Attributes accessible from the builder
    @property
    def name(self):
        return self._csr.name
    @property
    def access(self):
        return self._csr.access
    @property
    def width(self):
        raise SyntaxError("Actual width of {!r} should be queried using `len()` instead"
                          .format(self._csr))
    @property
    def desc(self):
        return self._csr.desc

    def _build_bus_from_reg(self):
        width = len(self._csr)
        access = self._csr.access
        self.bus = self._bus = Element(width, access,
                                       name="csr_"+self._csr.name)

    def _rename_field_sigs(self):
        """Change names of field signals and their reset signals for debugging
        """
        for field_name, field in self._csr._fields.items():
            field.signal.name = "csr_" + self._csr.name + "_field_" + field.name
            field.reset_strobe.name = "csr_" + self._csr.name + "_field_" + field.name + "_rststb"

    def __getitem__(self, key):
        """Slicing from the field list in units of bit
        """
        return self._csr.__getitem__(key)

    def __len__(self):
        """Get the width of the register (using ``len(<Register-object>)``).
        If register has not been specified with a width,
        this returns the total number of bits spanned by its fields.
        """
        return self._csr.__len__()

    def reset(self, sim=False):
        """Assign the default value to all the field signals in the register for exactly 1 clock.

        Parameters
        ----------
        sim : bool
            Flag to denote whether the logic is to be yielded for simulation purposes.
            If True, this returns a generator that yields the reset command from all of the fields.
            If False, this returns a list of assignment statements to be used by `m.d.domain_name +=`.
            Defaults to True.
        """
        if sim:
            yield from self._csr.reset(sim=True)
        else:
            return self._csr.reset(sim=False)


class _RegisterStandalone(_RegisterBase, Elaboratable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rename_field_sigs()
        self._build_bus_from_reg()

    def __enter__(self):
        self.f = self._csr.f
        return self

    def __exit__(self, e_type, e_value, e_tb):
        self.f = self.f_reader
        self._rename_field_sigs()
        self._build_bus_from_reg()

    def elaborate(self, platform):
        m = Module()
        # Read logic
        if self._csr.access.readable():
            with m.If(self._bus.r_stb):
                m.d.comb += _get_rw_bitmasked_logic("r", self._bus, self._csr)
            with m.Else():
                m.d.comb += self._bus.r_data.eq(0)
        # Write logic
        if self._csr.access.writable():
            reset_val = 0
            for _, field in self._csr._fields.items():
                reset_val |= (field._reset_value << field._startbit)
            csr_sig = Signal(len(self._csr), reset=reset_val)
            m.d.sync += csr_sig.eq(self._csr[:])
            with m.If(self._bus.w_stb):
                m.d.comb += _get_rw_bitmasked_logic("w", self._bus, self._csr)
            with m.Else():
                m.d.comb += self._csr[:].eq(csr_sig)
        # Reset logic
        for _, field in self._csr._fields.items():
            reset_now = Signal(reset=0, name=field.signal.name+"_rstnow")
            with m.If(field.reset_strobe):
                m.d.sync += [
                    field.reset_strobe.eq(0),
                    reset_now.eq(1)
                ]
            with m.If(reset_now):
                m.d.comb += field.signal.eq(field.reset_value)
                m.d.sync += reset_now.eq(0)
        return m


class _RegisterInBank(_RegisterBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rename_field_sigs()
        self._build_bus_from_reg()

    def __enter__(self):
        self.f = self._csr.f
        return self

    def __exit__(self, e_type, e_value, e_tb):
        self.f = self.f_reader
        self._rename_field_sigs()
        self._build_bus_from_reg()


class _RegisterBuilderFields(_BuilderProxy):
    def __iadd__(self, fields):
        if not isinstance(fields, Iterable):
            fields = [fields]
        for field in fields:
            self._builder._add_field(field)
        return self

    def __setattr__(self, name, obj):
        raise AttributeError("Cannot assign attribute '{}'; use '+=' to add a new field instead"
                             .format(name))

    def __getattr__(self, name):
        """Returns the field that is referenced by the queried name.
        """
        return self._builder._get_field(name)


class _RegisterBuilder:
    """A builder for building a control & status register representation.

    Parameters
    ----------
    name : str
        Name of the register.
    access : :class:`Element.Access`; or "r", "w", or "rw"
        Default read/write accessibility of the fields.
        If the field has already been specified with an access mode, this will be overridden.
    width : int or None
        Width of the register.
        If specified, the total width of its fields cannot exceed this value.
        If unspecified, register will resize depending on the total width of its fields.
        Instead of `reg.width`, use `len(reg)` to query the actual width.
    fields : list of Field or None
        Fields in this register.
        New fields can be added to the register using ``csr.f +=``.
    desc : str or None
        Description of the register. Optional.
    """

    def __init__(self, name, access, *, width=None, fields=None, desc=None):
        if not isinstance(name, str):
            raise TypeError("Name must be a string, not {!r}"
                            .format(name))
        self._name = name
        if not isinstance(access, Element.Access) and access not in ("r", "w", "rw"):
            raise ValueError("Access mode must be one of \"r\", \"w\", or \"rw\", not {!r}"
                             .format(access))
        self._access = Element.Access(access)
        if width is not None and not isinstance(width, int):
            raise TypeError("Width must be an integer, not {!r}"
                            .format(width))
        self._width = int(width) if width is not None else None
        if fields is not None and not isinstance(fields, list):
            raise TypeError("Fields must be a list, not {!r}"
                            .format(field))
        if desc is not None and not isinstance(desc, str):
            raise TypeError("Description must be a string, not {!r}"
                            .format(desc))
        self._desc = desc
        self._fields = OrderedDict()
        # Counter for total number of bits from the list of fields
        self._bitcount = 0
        # Appending CSR fields
        if fields is not None:
            for field in fields:
                self._add_field(field)
        # A CSR field list representation
        self.fields = self.f = _RegisterBuilderFields(self)

    @property
    def name(self):
        return self._name
    @property
    def access(self):
        return self._access
    @property
    def width(self):
        raise SyntaxError("Actual width of {!r} should be queried using `len()` instead"
                          .format(self))
    @property
    def desc(self):
        return self._desc
    @property
    def bitcount(self):
        return self._bitcount

    def __getitem__(self, key):
        """Slicing from the field list in units of bit
        """
        n = self._bitcount if self._width is None else self._width
        l = []
        if isinstance(key, int):
            l = self._get_field_sig_slice(key, key+1)
        elif isinstance(key, slice):
            start, stop, step = key.indices(n)
            if step != 1:
                l = [self._get_field_sig_slice(k, k+1) for k in range(start, stop, step)]
                # Flatten
                l = [y for x in l for y in x]
            else:
                l = self._get_field_sig_slice(start, stop)
        else:
            raise TypeError("Cannot index value with {!r}"
                            .format(key))
        # Return a Cat nMigen object instead of a list
        if l is None:
            raise ValueError("Cannot find any fields in the slice {!r}"
                             .format(key))
        return Cat(*l)

    def _add_field(self, field):
        if not isinstance(field, Field):
            raise TypeError("{!r} is not a Field object"
                            .format(field))
        if field.name in self._fields:
            raise NameError("Field {!r} has a name that is already present in this register"
                            .format(field))
        # Assign start / end bit if not already specified
        if field.startbit is None:
            field._startbit = self._bitcount
            field._endbit = field.startbit + field.width - 1
        # Check for start / end bit overlapping
        if _is_bit_overlapping(field.startbit, field.endbit, [(f.startbit,f.endbit) for (k,f) in self._fields.items()]):
            raise AttributeError("Field {!r} (starting at bit {} and ending at bit {}) has bit locations that has been occupied by an existing field"
                                 .format(field, field.startbit, field.endbit))
        # Calculate total number of bits
        self._bitcount = field.endbit+1 if field.endbit > self._bitcount-1 else self._bitcount
        # If total number of bits exceeds register width, raise error
        if self._width is not None and self._bitcount > self._width:
            raise AttributeError("This register does not have enough bit width for field {!r} of width {}"
                                 .format(field, field.width))
        # If field has a higher accessibility than register, raise error
        if field.access is not None and not self._access.does_allow(field.access):
            raise AttributeError("Field {!r} ({}) has a higher accessibility than this register ({})"
                                 .format(field, field.access, self._access))
        # If field doesn't specify accessibiltiy, inherit it from register-level
        if field.access is None:
            field._access = self._access
        # Add field to list
        self._fields[field.name] = field

    def _get_field(self, name):
        if name in self._fields:
            return self._fields[name]
        else:
            raise AttributeError("No field named '{}' exists".format(name))

    def _get_field_sig_slice(self, start, end):
        n = self._bitcount if self._width is None else self._width
        if start < 0:
            start += n
            end += n
        if end < 0:
            end += n
        if start < 0 or end > n:
            raise IndexError("Slice interval [{}, {}) must be within [-{}, {})"
                             .format(start, end, -n, n))
        if start > end:
            raise IndexError("Slice start {} must be less than slice end {}"
                             .format(start, end))
        # Get a list of fields covered (even partially) by the slice
        fl = [self._fields[name] for name in self._fields.keys() if (
                self._fields[name].endbit >= start and self._fields[name].startbit < end
             )]
        # Make slices of individual signals
        l = [f.signal[0 if f.startbit>=start else start-f.startbit : f.width if f.endbit<end else -(f.endbit+1-end)] for f in fl]
        if len(l) == 0:
            return None
        return l

    def _get_access_bitmask(self, access):
        if not isinstance(access, Element.Access) and access not in ("r", "w", "rw"):
            raise ValueError("Access mode must be one of \"r\", \"w\", or \"rw\", not {!r}"
                             .format(access))
        access = Element.Access(access)
        bitmask = 0
        for name, field in self._fields.items():
            # Skip fields when the enquired access mode is excluded from the field access mode
            if not field.access.does_allow(access):
                continue
            startbit, stopbit = field.startbit, field.endbit
            for bit in range(startbit, stopbit+1):
                bitmask |= (1 << bit)
        return bitmask

    def reset(self, sim=False):
        """Assign the default value to all the field signals in the register for exactly 1 clock.

        Parameters
        ----------
        sim : bool
            Flag to denote whether the logic is to be yielded for simulation purposes.
            If True, this returns a generator that yields the reset command from all of the fields.
            If False, this returns a list of assignment statements to be used by `m.d.domain_name +=`.
            Defaults to True.
        """
        if len(self._fields) == 0:
            raise ValueError("At least one field must be present for a register reset")
        if sim:
            for _,field in self._fields.items():
                yield field.reset()
        else:
            return [field.reset() for _,field in self._fields.items()]

    def __len__(self):
        """Get the width of the register (using ``len(<Register-object>)``,
        in a `with <Register-object> as register` block`).
        If register has not been specified with a width,
        this returns the total number of bits spanned by its fields.
        """
        return self._bitcount if self._width is None else self._width

    def __repr__(self):
        return "(csr {})".format(self._name)


class Field:
    """A control & status register field representation

    Parameters
    ----------
    name : str
        Name of the field.
    access : :class:`Element.Access`; or "r", "w", or "rw"; or None
        Default read/write accessibility of the field.
        Note that, if unspecifie, when this field is added to a CSR, this will inherit from the CSR access mode.
    width : int
        Size of the field.
        If unspecified, the field is of width 1.
    startbit : int or None
        Location of the first bit of the field in the CSR to which the field is added to.
        If unspecified, the first bit is set to the bit immediately after the current final bit of the CSR.
    reset : int
        Default value of the field.
        If unspecified, the reset value is 0.
    desc : str or None
        Description of the register. Optional.
    """

    class _FieldBuilderEnumsReaderProxy(_BuilderAttrReaderProxy):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
        def __getattr__(self, name):
            if name in object.__getattribute__(self, "_dict"):
                return object.__getattribute__(self, "_dict")[name]
            raise AttributeError(("Cannot get attribute '{}'; "+
                                  "instead, use `<{}-object>.Enums.{}.value` to get the enumerated value")
                                 .format(name,
                                         parent_class.__name__, name))

    def __init__(self, name, *args, access=None, width=1, startbit=None, reset_value=0, desc=None, **kwargs):
        self._field = _FieldBuilder(name, *args, width=width, **kwargs)
        if not isinstance(name, str):
            raise TypeError("Name must be a string, not {!r}"
                            .format(name))
        self._name = name
        if access is not None and not isinstance(access, Element.Access) and access not in ("r", "w", "rw"):
            raise TypeError("Access mode must be \"r\", \"w\", \"rw\", or None, not {!r}"
                            .format(access))
        self._access = Element.Access(access) if access is not None else None
        if not isinstance(width, int):
            raise TypeError("Size must be an integer, not {!r}"
                            .format(width))
        self._width = int(width)
        if not isinstance(reset_value, int):
            raise TypeError("Reset value must be an integer, not {!r}"
                            .format(reset_value))
        self._reset_value = reset_value
        if desc is not None and not isinstance(desc, str):
            raise TypeError("Description must be a string, not {!r}"
                            .format(desc))
        self._desc = desc
        # Define the start / end bit position in the register
        self._startbit, self._endbit = None, None
        if startbit is not None:
            self._startbit = startbit
            self._endbit = self._startbit+self._width-1         # Exact bit where this field ends
        # A field Signal representation
        self._signal = Signal(shape=self._width,
                              reset=self._reset_value,
                              reset_less=True,
                              name=self._name+"_signal")
        self.sig = self.s = self.signal
        # A reset signal for the field signal
        self._reset_strobe = Signal(reset=0)
        self.rst = self.reset_strobe
        # Build Enums from self._field._enums, if already exists
        self._build_field_enums()
        # Context manager: 
        # - If outside a `with` block, self.e returns a special reader
        # - If inside a `with` block, self.e returns a builder
        self.e_reader = Field._FieldBuilderEnumsReaderProxy(self._field.e, "e", Field, [tuple, str])
        self.e = self.e_reader

    @property
    def name(self):
        return self._name
    @property
    def access(self):
        return self._access
    @property
    def width(self):
        return self._width
    @property
    def reset_value(self):
        return self._reset_value
    @property
    def desc(self):
        return self._desc
    @property
    def startbit(self):
        return self._startbit
    @property
    def endbit(self):
        return self._endbit
    @property
    def signal(self):
        return self._signal
    @property
    def reset_strobe(self):
        return self._reset_strobe

    # A dynamically-created Enum class
    Enums = None
    def _build_field_enums(self):
        # If this field uses enums:
        if self._field._enums:
            # (Re-)build the Enums class
            self.Enums = Enum('Enums', self._field._enums)
            # (Re-)build the decoder for the signal
            self._signal = Signal(shape=self._width, reset=self._reset_value, reset_less=True,
                                  decoder=self.Enums, name=self._name+"_signal")

    def __enter__(self):
        self.e = self._field.e
        return self

    def __exit__(self, e_type, e_value, e_tb):
        self.e = self.e_reader
        self._build_field_enums()

    def __getitem__(self, key):
        """Slicing from the field signal in units of bit
        """
        return self._signal[key]

    def reset(self):
        """Assign the default value to the field signal for exactly 1 clock.

        Returns
        -------
        Assign
            Assignment statement that can be used in combinatorial or synchronous context.
        """
        return Assign(self._reset_strobe, 1, src_loc_at=1)


class _FieldBuilderEnums(_BuilderProxy):
    def __iadd__(self, enums):
        if not isinstance(enums, Iterable):
            enums = [enums]
        for enum in enums:
            self._builder._add_enum(enum)
        return self

    def __setattr__(self, name, obj):
        raise AttributeError("Cannot assign enum '{}'; use '+=' to add a new enum instead"
                             .format(name))

    def __getattr__(self, name):
        """Returns the enum value that is referenced by the queried name.
        Note that, outside of the `with field` block,
        the enum value can be accessed by `field.Enums.<enum-name>.value`.
        """
        return self._builder._get_enum_val(name)


class _FieldBuilder:
    """A builder for building enums for the field

    Parameters
    ----------
    width : int
        Size of the field, which must be at least greater than all the enum values.
        If unspecified, the field is of width 1.
    enums : list of tuple like (str, int), or list of str, or None
        List of enumerated values (enums) to be used by this field.
        If a tuple like (str, int) is used, the int object (value) is be mapped to the str object (name).
        If a str is used, 0 is mapped to the first str object added (name), and the next integer following the current greatest value in the enum list is mapped to the str object (name).
        Within the `with` block, new enums can be added to the field using ``field.e +=``.
    """
    def __init__(self, name, *, width=1, enums=None, **kwargs):
        self._name = name
        self._width = width
        if enums is not None and not isinstance(enums, list):
            raise TypeError("Enum dictionary must be a list of either (name, value) pairs or names, not {!r}"
                            .format(enums))
        self._enums = OrderedDict()
        # Appending enum values
        if enums is not None:
            for enum in enums:
                self._add_enum(enum)
        # A field enum list representation
        self.enums = self.e = _FieldBuilderEnums(self)

    @property
    def name(self):
        return self._name
    @property
    def width(self):
        return self._width

    def _add_enum(self, enum):
        name, value = None, None
        if isinstance(enum, tuple) and len(enum) == 2:
            if not isinstance(enum[0], str) or not isinstance(enum[1], int):
                raise TypeError("In enum dict, a tuple entry must be (name, value), not {!r}"
                                .format(enum))
            name, value = enum[0], enum[1]
        elif isinstance(enum, str):
            if len(enum) == 0:
                raise TypeError("In enum dict, a str entry should have non-empty str as name")
            # If there are enums, this new enum will have the value of: max value in the enum list + 1
            if len(self._enums):
                name, value = enum, max([v for _,v in self._enums.items()])+1
            # Otherwise, this new enum will have the value of zero
            else:
                name, value = enum, 0
        else:
            raise TypeError("In enum dict, an entry must be a tuple (name, value) or a non-empty str as name"
                            .format(enum))
        # If enum is too big for the field, raise error
        enum_width = utils.bits_for(abs(value), require_sign_bit=value<0)
        if enum_width > self._width:
            raise ValueError("Enum '{}' has the value {}, which contains too many bits ({}) for this field of width {}"
                             .format(name, value, enum_width, self._width))
        # Add enum to list
        self._enums[name] = value

    def _get_enum_val(self, name):
        if name in self._enums:
            return self._enums[name]
        else:
            raise AttributeError("No enum named '{}' exists".format(name))

    def __repr__(self):
        return "(csrfield {})".format(self._name)