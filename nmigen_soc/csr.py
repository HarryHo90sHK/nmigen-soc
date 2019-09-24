from enum import Enum
from collections import OrderedDict
from migen import *


__all__ = ["CSRField"]


Access = Enum('Access', ('R', 'W', 'R_W', 'WONCE', 'R_WONCE'))
ACCESS_R       = Access.R
ACCESS_W       = Access.W
ACCESS_R_W     = Access.R_W
ACCESS_WONCE   = Access.WONCE
ACCESS_R_WONCE = Access.R_WONCE


class CSRGeneric():
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
        self.fields = OrderedDict()
        # Counter for total number of bits from the list of fields
        self.bitcount = 0
        # Appending CSR fields
        for field in fields:
            self._add_field(field)

    def _add_field(self, field):
        if not isinstance(field, CSRField):
            raise TypeError("{!r} is not a CSRField object"
                            .format(field))
        if field.name in self.fields:
            raise NameError("Field {!r} has a name that is already present in this register"
                            .format(field))
        # Assign bit position and count total number of bits
        field.bitpos = self.bitcount = self.bitcount+field.size
        # Add field to list
        self.fields[field.name] = field

    def __iadd__(self, fields):
        # TODO
        pass


class CSRField():
    """
    """

    def __init__(self, name, size=1, offset=0, reset=0, access=None):
        self.name = name
        self.size = size
        self.offset = offset
        self.reset = reset
        if not isinstance(access, Access):
            raise TypeError("{!r} is not a valid access type: should be an Access instance like ACCESS_R"
                            .format(access))
        self.access = access
        self.bitpos = None
