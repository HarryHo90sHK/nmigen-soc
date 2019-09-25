from enum import Enum
from collections import OrderedDict
from nmigen import *


__all__ = ["CSRField"]


Access = Enum('Access', ('R', 'W', 'R_W', 'WONCE', 'R_WONCE'))
ACCESS_R       = Access.R
ACCESS_W       = Access.W
ACCESS_R_W     = Access.R_W
ACCESS_WONCE   = Access.WONCE
ACCESS_R_WONCE = Access.R_WONCE


class _CSRBuilderRoot:
    """
    """

    def __init__(self, builder):
        self._builder = builder

    def __getattr__(self, name):
        # __getattr__ in superclass is called first
        raise AttributeError("'{}' object has no attribute '{}'"
                             .format(type(self).__name__, name))

    # TODO: Make abstract methods for add/get_fields


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
        raise AttributeError("Cannot assign '{}' attribute; use '+=' to add a new field instead"
                             .format(name))

    def __getattr__(self, name):
        return self._builder._get_field(name)


class CSRGeneric(_CSRBuilderRoot):
    """
    """

    def __init__(self, name, fields, offset=0, access=None, atomic_r=False, atomic_w=False):
        self.name = name
        if not isinstance(fields, list):
            raise TypeError("{!r} is not a list"
                            .format(field))
        self.offset = offset
        if not isinstance(access, Access):
            raise TypeError("{!r} is not a valid access type: should be an Access instance like ACCESS_R"
                            .format(access))
        self.access = access
        self.atomic_r = atomic_r
        self.atomic_w = atomic_w
        self._fields = OrderedDict()
        # Counter for total number of bits from the list of fields
        self.bitcount = 0
        # Appending CSR fields
        for field in fields:
            self._add_field(field)
        # A CSR field list representation
        self.fields = self.f = _CSRBuilderFields(self)

    def _add_field(self, field):
        if not isinstance(field, CSRField):
            raise TypeError("{!r} is not a CSRField object"
                            .format(field))
        if field.name in self._fields:
            raise NameError("Field {!r} has a name that is already present in this register"
                            .format(field))
        # Assign bit position and count total number of bits
        field.bitpos = self.bitcount = self.bitcount+field.size
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


class CSRField():
    """
    """

    def __init__(self, name, size=1, offset=0, reset=0, access=None):
        self.name = name
        self.size = size
        self.offset = offset
        self.reset = reset
        if not isinstance(access, Access) and access is not None:
            raise TypeError("{!r} is not a valid access type: should be an Access instance like ACCESS_R"
                            .format(access))
        self.access = access
        self.bitpos = None
