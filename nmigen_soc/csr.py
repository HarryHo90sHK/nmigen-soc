from enum import Enum
from collections import OrderedDict
from nmigen import *


__all__ = ["Access", "ACCESS_R", "ACCESS_W", "ACCESS_R_W", "ACCESS_WONCE", "ACCESS_R_WONCE", 
           "CSRGeneric", "CSRField"]


Access = Enum('Access', ('R', 'W', 'R_W', 'WONCE', 'R_WONCE'))
ACCESS_R       = Access.R
ACCESS_W       = Access.W
ACCESS_R_W     = Access.R_W
ACCESS_WONCE   = Access.WONCE
ACCESS_R_WONCE = Access.R_WONCE


def is_bit_overlapping(startbit, endbit, bitrange_list):
    """Helper function for checking if a bit range has overlapped with existing bit ranges
    """
    for bitrange in bitrange_list:
        if max(0, min(endbit, bitrange[1]) - max(startbit, bitrange[0]) + 1) != 0:
            return True
    return False


class _CSRBuilderRoot:
    """
    """

    def __init__(self, builder):
        self._builder = builder

    def __getattr__(self, name):
        # __getattr__ in superclass is called first
        raise AttributeError("'{}' object has no attribute '{}'"
                             .format(type(self).__name__, name))


class _CSRBuilderFields:
    """
    """

    def __init__(self, builder):
        object.__setattr__(self, "_builder", builder)   # Using "basic" __setattr__()

    def __iadd__(self, fields):
        for field in tools.flatten([fields]):
            self._builder._add_field(field)
        # Return itself so that it won't get destroyed
        return self

    def __setattr__(self, name, obj):
        raise AttributeError("Cannot assign attribute '{}'; use '+=' to add a new field instead"
                             .format(name))

    def __getattr__(self, name):
        return self._builder._get_field(name)


class _CSRBuilderFieldEnums:
    """
    """

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


class CSRGeneric(_CSRBuilderRoot):
    """A control & status register representation

    Parameters
    ----------
    name : str
        Name of the register
    access : Access
        Default read/write accessibility of the fields.
        If the field has already been specified with an access type, this will be overridden.
    size : int or None
        Size of the register.
        If unspecified, register will resize depending on the total size of its fields.
    fields : list of Field or None
        Fields in this register.
        New fields can be added to the register using `csr.f +=`.
    atomic_r : bool
        Whether reading from this register is atomic or not
    atomic_w : bool
        Whether writing to this register is atomic or not
    desc : str or None
        Description of the register. Optional.
    """

    def __init__(self, name, access, size=None, fields=None, atomic_r=False, atomic_w=False, desc=None):
        if not isinstance(name, str):
            raise TypeError("{!r} is not a string"
                            .format(name))
        self.name = name
        if not isinstance(access, Access):
            raise TypeError("{!r} is not a valid access type: should be an Access instance like ACCESS_R"
                            .format(access))
        self.access = access
        if size is not None and not isinstance(size, int):
            raise TypeError("{!r} is not an integer"
                            .format(size))
        self.size = size
        if fields is not None and not isinstance(fields, list):
            raise TypeError("{!r} is not a list"
                            .format(field))
        if not isinstance(atomic_r, int):
            raise TypeError("{!r} is not True or False"
                            .format(atomic_r))
        self.atomic_r = atomic_r
        if not isinstance(atomic_w, int):
            raise TypeError("{!r} is not True or False"
                            .format(atomic_w))
        self.atomic_w = atomic_w
        if desc is not None and not isinstance(desc, str):
            raise TypeError("{!r} is not a string"
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
        n = self.bitcount if self.size is None else self.size
        l = []
        if isinstance(key, int):
            l = self._get_field_sig_slice(key, key+1)
        elif isinstance(key, slice):
            start, stop, step = key.indices(n)
            if step != 1:
                l = tools.flatten([self._get_field_sig_slice(k, k+1) for k in range(start, stop, step)])
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
            field.endbit = field.startbit + field.size - 1
        # Check for start / end bit overlapping
        if is_bit_overlapping(field.startbit, field.endbit, [(f.startbit,f.endbit) for (k,f) in self._fields.items()]):
            raise AttributeError("Field {!r} (starting at bit {} and ending at bit {}) has bit locations that has been occupied by an existing field"
                                 .format(field, field.startbit, field.endbit))
        # Calculate total number of bits
        self.bitcount = field.endbit+1 if field.endbit > self.bitcount-1 else self.bitcount
        # If total number of bits exceeds register size, raise error
        if self.size is not None and self.bitcount > self.size:
            raise AttributeError("This register does not have enough bit width for field {!r} of size {}"
                                 .format(field, field.size))
        # If field doesn't specify accessibiltiy, inherit it from register-level
        if field.access is None:
            field.access = self.access
        # Add field to list
        self._fields[field.name] = field

    def _get_field(self, name):
        if name in self._fields:
            return self._fields[name]
        else:
            raise AttributeError("No field named '{}' exists".format(name))

    def _get_field_sig(self, name):
        if name in self._fields:
            return self._fields[name]._signal
        else:
            raise AttributeError("No field named '{}' exists".format(name))

    def _get_field_sig_slice(self, start, end):
        n = self.bitcount if self.size is None else self.size
        if start not in range(-n, n):
            raise IndexError("Slice cannot start at bit {} for a {}-bit value"
                             .format(start, n))
        if start < 0:
            start += n
        if end not in range(-self.get_size()+1, self.get_size()+1):
            raise IndexError("Slice cannot end before bit {} for a {}-bit value"
                             .format(end, n))
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
        l = [f._signal[0 if f.startbit>=start else start-f.startbit : f.size if f.endbit<end else -(f.endbit+1-end)] for f in fl]
        if len(l) == 0:
            return None
        return l

    def get_size(self):
        """Get the size of the register.
        If register has not been specified with a size, this returns the total number of bits spanned by its fields
        """
        return self.bitcount if self.size is None else self.size

    def get_signal(self):
        """Get the entire signal for the register (Cat'ed and Slice'd). 
        """
        return Cat(*self._get_field_sig_slice(0, self.get_size()))

    def __repr__(self):
        return "(csr {})".format(self.name)


class CSRField(_CSRBuilderRoot):
    """A control & status register field representation

    Parameters
    ----------
    name : str
        Name of the field
    access : Access or None
        Default read/write accessibility of the field.
        Note that, if unspecifie, when this field is added to a CSR, this will inherit from the CSR access type.
    size : int
        Size of the field.
        If unspecified, the field is of size 1.
    startbit : int or None
        Location of the first bit of the field in the CSR to which the field is added to.
        If unspecified, the first bit is set to the bit immediately after the current final bit of the CSR.
    reset : int
        Reset (synchronous) or default (combinatorial) value of the field.
        If unspecified, the reset value is 0.
    enums : list of tuple like (str, int), or list of str, or None
        List of enumerated values (enums) to be used by this field.
        If a tuple like (str, int) is used, the int object (value) is be mapped to the str object (name).
        If a str is used, the next integer following the current greatest value in the enum list is mapped to the str object (name).
        New enums can be added to the field using `field.e +=`.
    desc : str or None
        Description of the register. Optional.
    """

    def __init__(self, name, access=None, size=1, startbit=None, reset=0, enums=None, desc=None):
        if not isinstance(name, str):
            raise TypeError("{!r} is not a string"
                            .format(name))
        self.name = name
        if access is not None and not isinstance(access, Access):
            raise TypeError("{!r} is not a valid access type: should be an Access instance like ACCESS_R"
                            .format(access))
        self.access = access
        if not isinstance(size, int):
            raise TypeError("{!r} is not an integer"
                            .format(size))
        self.size = size
        self.reset = reset
        if not isinstance(access, Access) and access is not None:
            raise TypeError("{!r} is not a valid access type: should be an Access instance like ACCESS_R"
                            .format(access))
        if enums is not None and not isinstance(enums, list):
            raise TypeError("{!r} is not a list"
                            .format(enums))
        if desc is not None and not isinstance(desc, str):
            raise TypeError("{!r} is not a string"
                            .format(desc))
        self.desc = desc
        self._signal = Signal(shape=self.size, reset=self.reset)
        self._enums = OrderedDict()
        # Define the start / end bit position in the register
        self.startbit, self.endbit = None, None
        if startbit is not None:
            self.startbit = startbit
            self.endbit = self.startbit+self.size-1      # Exact bit where this field ends
        # Appending enum values
        if enums is not None:
            for enum in enums:
                self._add_enum(enum)
        # A field Signal representation
        self.signal = self.sig = self.s = self._signal
        # A field enum list representation
        self.enums = self.e = _CSRBuilderFieldEnums(self)

    def _add_enum(self, enum):
        name, value = None, None
        if isinstance(enum, tuple) and len(enum) == 2:
            if not isinstance(enum[0], str) or not isinstance(enum[1], int):
                raise TypeError("{!r} is not a valid enum tuple: should be (name, value)"
                                .format(enum))
            name, value = enum[0], enum[1]
        elif isinstance(enum, str):
            if len(enum) == 0:
                raise TypeError("'{}' is not a non-empty str as an enum name"
                                .format(enum))
            # Enum values start at 0 by default
            name, value = enum, len(self._enums)
        else:
            raise TypeError("{!r} is not a valid enum format: should be either a tuple (name, value) or a non-empty str as name"
                            .format(enum))
        # If enum is too big for the field, raise error
        if tools.bits_for(abs(value), require_sign_bit=value<0) > self.size:
            raise ValueError("Enum '{}' has the value {}, which is too large for this field of size {}"
                             .format(name, value, self.size))
        # Add enum to list
        self._enums[name] = value

    def _get_enum_val(self, name):
        if name in self._enums:
            return self._enums[name]
        else:
            raise AttributeError("No enum named '{}' exists".format(name))

    def __repr__(self):
        return "(csrfield {})".format(self.name)
