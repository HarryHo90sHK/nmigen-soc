from enum import Enum
from collections import OrderedDict
from nmigen import *
from .bus import *


__all__ = ["CSRRegister", "CSRField"]


class CSRRegister(Elaboratable):
    def __init__(self, *args, **kwargs):
        self._reg = _CSRRegisterBuilder(*args, **kwargs)
        self.width = len(self._reg)
        self.access = self._reg.access
        self._bus = CSRElement(self.width, self.access, 
                               name="csr_"+self._reg.name)

    def __enter__(self):
        return self._reg

    def __exit__(self, e_type, e_value, e_tb):
        self.width = len(self._reg)
        self.access = self._reg.access
        self._bus = CSRElement(self.width, self.access, 
                               name="csr_"+self._reg.name)

    def elaborate(self, platform):
        # TODO: Supposedly a CSRRegister object should be added as a submodule after the `with` block
        m = Module()
        # Read logic
        m.d.comb += [
            self._bus.r_data[i].eq(self._reg[i]) for i,v in
            enumerate(format(self._reg._get_access_bitmask("r"), "b")[::-1]) if v=="1"
        ]
        # Write logic
        m.d.sync += [
            self._reg[i].eq(self._bus.w_data[i]) for i,v in
            enumerate(format(self._reg._get_access_bitmask("w"), "b")[::-1]) if v=="1"
        ]
        return m


def _is_bit_overlapping(startbit, endbit, bitrange_list):
    """Helper function for checking if a bit range has overlapped with existing bit ranges
    """
    for bitrange in bitrange_list:
        if max(0, min(endbit, bitrange[1]) - max(startbit, bitrange[0]) + 1) != 0:
            return True
    return False


class _CSRBuilderFields:
    def __init__(self, builder):
        object.__setattr__(self, "_builder", builder)   # Using "basic" __setattr__()

    def __iadd__(self, fields):
        for field in fields:
            self._builder._add_field(field)
        # Return itself so that it won't get destroyed
        return self

    def __setattr__(self, name, obj):
        raise AttributeError("Cannot assign attribute '{}'; use '+=' to add a new field instead"
                             .format(name))

    def __getattr__(self, name):
        return self._builder._get_field(name)


class _CSRRegisterBuilder:
    """A control & status register representation.

    Reading from and writing to the register is now atomic by default.

    Parameters
    ----------
    name : str
        Name of the register.
    access : "r", "w", or "rw"
        Default read/write accessibility of the fields.
        If the field has already been specified with an access mode, this will be overridden.
    width : int or None
        Width of the register.
        If unspecified, register will resize depending on the total width of its fields.
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
        self.name = name
        if access not in ("r", "w", "rw"):
            raise TypeError("Access mode must be \"r\", \"w\", or \"rw\", not {!r}"
                            .format(access))
        self.access = access
        if width is not None and not isinstance(width, int):
            raise TypeError("Width must be an integer, not {!r}"
                            .format(width))
        self.width = int(width) if width is not None else None
        if fields is not None and not isinstance(fields, list):
            raise TypeError("Fields must be a list, not {!r}"
                            .format(field))
        if desc is not None and not isinstance(desc, str):
            raise TypeError("Description must be a string, not {!r}"
                            .format(desc))
        self.desc = desc
        self._fields = OrderedDict()
        # Counter for total number of bits from the list of fields
        self.bitcount = 0
        # Appending CSR fields
        if fields is not None:
            for field in fields:
                self._add_field(field)
        # A CSR field list representation
        self.fields = self.f = _CSRBuilderFields(self)

    def __getitem__(self, key):
        """Slicing from the field list in units of bit
        """
        n = self.bitcount if self.width is None else self.width
        l = []
        if isinstance(key, int):
            l = self._get_field_sig_slice(key, key+1)
        elif isinstance(key, slice):
            start, stop, step = key.indices(n)
            if step != 1:
                l = [self._get_field_sig_slice(k, k+1) for k in range(start, stop, step)]
                # Flatten
                l = [y for y in x for x in l]
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
        if not isinstance(field, CSRField):
            raise TypeError("{!r} is not a CSRField object"
                            .format(field))
        if field.name in self._fields:
            raise NameError("Field {!r} has a name that is already present in this register"
                            .format(field))
        # Assign start / end bit if not already specified
        if field.startbit is None:
            field.startbit = self.bitcount
            field.endbit = field.startbit + field.width - 1
        # Check for start / end bit overlapping
        if _is_bit_overlapping(field.startbit, field.endbit, [(f.startbit,f.endbit) for (k,f) in self._fields.items()]):
            raise AttributeError("Field {!r} (starting at bit {} and ending at bit {}) has bit locations that has been occupied by an existing field"
                                 .format(field, field.startbit, field.endbit))
        # Calculate total number of bits
        self.bitcount = field.endbit+1 if field.endbit > self.bitcount-1 else self.bitcount
        # If total number of bits exceeds register width, raise error
        if self.width is not None and self.bitcount > self.width:
            raise AttributeError("This register does not have enough bit width for field {!r} of width {}"
                                 .format(field, field.width))
        # If field has a higher accessibility than register, raise error
        if ((field.access == "r" and self.access == "w") or
            (field.access == "w" and self.access == "r")):
            raise AttributeError("Field {!r} ({}) has a higher accessibility than this register ({})"
                                 .format(field, field.access, self.access))
        # If field doesn't specify accessibiltiy, inherit it from register-level
        if field.access is None:
            field.access = self.access
        # Add field to list
        self._fields[field.name] = field
        # Change field signal name for debugging
        self._fields[field.name]._signal.name = "csr_" + self.name + "__field_" + field.name

    def _get_field(self, name):
        if name in self._fields:
            return self._fields[name]
        else:
            raise AttributeError("No field named '{}' exists".format(name))

    def _get_field_sig_slice(self, start, end):
        n = self.bitcount if self.width is None else self.width
        if start < 0:
            start += n
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
        l = [f._signal[0 if f.startbit>=start else start-f.startbit : f.width if f.endbit<end else -(f.endbit+1-end)] for f in fl]
        if len(l) == 0:
            return None
        return l

    def _get_access_bitmask(self, access):
        if access not in ("r", "w", "rw"):
            raise ValueError("Access mode must be one of \"r\", \"w\", or \"rw\", not {!r}"
                             .format(access))
        bitmask = 0
        for name, field in self._fields.items():
            # Skip fields when the enquired access mode is excluded from the field access mode
            if access not in field.access:
                continue
            startbit, stopbit = field.startbit, field.endbit
            for bit in range(startbit, stopbit+1):
                bitmask |= (1 << bit)
        return bitmask

    def __len__(self):
        """Get the width of the register (using ``len(csrregister)``).
        If register has not been specified with a width, this returns the total number of bits spanned by its fields
        """
        return self.bitcount if self.width is None else self.width

    def __repr__(self):
        return "(csr {})".format(self.name)


class _CSRBuilderFieldEnums:
    def __init__(self, builder):
        object.__setattr__(self, "_builder", builder)   # Using "basic" __setattr__()

    def __iadd__(self, enums):
        for enum in enums:
            self._builder._add_enum(enum)
        # Return itself so that it won't get destroyed
        return self

    def __setattr__(self, name, obj):
        raise AttributeError("Cannot assign enum '{}'; use '+=' to add a new enum instead"
                             .format(name))

    def __getattr__(self, name):
        return self._builder._get_enum_val(name)


class CSRField:
    """A control & status register field representation

    Parameters
    ----------
    name : str
        Name of the field.
    access : "r", "w", "rw", or None
        Default read/write accessibility of the field.
        Note that, if unspecifie, when this field is added to a CSR, this will inherit from the CSR access mode.
    width : int
        Size of the field.
        If unspecified, the field is of width 1.
    startbit : int or None
        Location of the first bit of the field in the CSR to which the field is added to.
        If unspecified, the first bit is set to the bit immediately after the current final bit of the CSR.
    reset : int
        Reset (synchronous) or default (combinatorial) value of the field.
        If unspecified, the reset value is 0.
    enums : list of tuple like (str, int), or list of str, or None
        List of enumerated values (enums) to be used by this field.
        If a tuple like (str, int) is used, the int object (value) is be mapped to the str object (name).
        If a str is used, 0 is mapped to the first str object added (name), and the next integer following the current greatest value in the enum list is mapped to the str object (name).
        New enums can be added to the field using ``field.e +=``.
    desc : str or None
        Description of the register. Optional.
    """

    def __init__(self, name, *, access=None, width=1, startbit=None, reset=0, enums=None, desc=None):
        if not isinstance(name, str):
            raise TypeError("Name must be a string, not {!r}"
                            .format(name))
        self.name = name
        if access is not None and access not in ("r", "w", "rw"):
            raise TypeError("Access mode must be \"r\", \"w\", \"rw\", or None, not {!r}"
                            .format(access))
        self.access = access
        if not isinstance(width, int):
            raise TypeError("Size must be an integer, not {!r}"
                            .format(width))
        self.width = int(width)
        if not isinstance(reset, int):
            raise TypeError("Reset value must be an integer, not {!r}"
                            .format(reset))
        self.reset = reset
        if enums is not None and not isinstance(enums, list):
            raise TypeError("Enum dictionary must be a list of either (name, value) pairs or names, not {!r}"
                            .format(enums))
        if desc is not None and not isinstance(desc, str):
            raise TypeError("Description must be a string, not {!r}"
                            .format(desc))
        self.desc = desc
        self._signal = Signal(shape=self.width, reset=self.reset)
        self._enums = OrderedDict()
        # Define the start / end bit position in the register
        self.startbit, self.endbit = None, None
        if startbit is not None:
            self.startbit = startbit
            self.endbit = self.startbit+self.width-1      # Exact bit where this field ends
        # Appending enum values
        if enums is not None:
            for enum in enums:
                self._add_enum(enum)
        # A field Signal representation
        self.signal = self.sig = self.s = self._signal
        # A field enum list representation
        self.enums = self.e = _CSRBuilderFieldEnums(self)

    def __getitem__(self, key):
        """Slicing from the field signal in units of bit
        """
        return self._signal[key]

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
        if enum_width > self.width:
            raise ValueError("Enum '{}' has the value {}, which contains too many bits ({}) for this field of width {}"
                             .format(name, value, enum_width, self.width))
        # Add enum to list
        self._enums[name] = value

    def _get_enum_val(self, name):
        if name in self._enums:
            return self._enums[name]
        else:
            raise AttributeError("No enum named '{}' exists".format(name))

    def __repr__(self):
        return "(csrfield {})".format(self.name)
