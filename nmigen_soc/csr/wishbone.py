from nmigen import *
from nmigen.utils import log2_int

from . import Interface as CSRInterface
from ..wishbone import Interface as WishboneInterface


__all__ = ["WishboneCSRBridge"]


class WishboneCSRBridge(Elaboratable):
    """Wishbone to CSR bridge.

    A bus bridge for accessing CSR registers from Wishbone. This bridge supports any Wishbone
    data width greater or equal to CSR data width and performs appropriate address translation.

    Latency
    -------

    Reads and writes always take ``self.data_width // csr_bus.data_width + 1`` cycles to complete,
    regardless of the select inputs. Write side effects occur simultaneously with acknowledgement.

    Parameters
    ----------
    csr_bus : :class:`..csr.Interface`
        CSR bus driven by the bridge.
    data_width : int or None
        Wishbone bus data width. If not specified, defaults to ``csr_bus.data_width``.

    Attributes
    ----------
    wb_bus : :class:`..wishbone.Interface`
        Wishbone bus provided by the bridge.
    """
    def __init__(self, csr_bus, *, data_width=None):
        if not isinstance(csr_bus, CSRInterface):
            raise ValueError("CSR bus must be an instance of CSRInterface, not {!r}"
                             .format(csr_bus))
        if csr_bus.data_width not in (8, 16, 32, 64):
            raise ValueError("CSR bus data width must be one of 8, 16, 32, 64, not {!r}"
                             .format(csr_bus.data_width))
        if data_width is None:
            data_width = csr_bus.data_width

        self.csr_bus = csr_bus
        self.wb_bus  = WishboneInterface(
            addr_width=max(0, csr_bus.addr_width - log2_int(data_width // csr_bus.data_width)),
            data_width=data_width,
            granularity=csr_bus.data_width,
            name="wb")

        # Since granularity of the Wishbone interface matches the data width of the CSR bus,
        # no width conversion is performed, even if the Wishbone data width is greater.
        self.wb_bus.memory_map.add_window(self.csr_bus.memory_map)

    def elaborate(self, platform):
        csr_bus = self.csr_bus
        wb_bus  = self.wb_bus

        m = Module()

        # Define a signal counting from 0 to len(Wishbone SEL) + 1
        counter = Signal(range(len(wb_bus.sel) + 2))

        with m.If(wb_bus.cyc & wb_bus.stb):
            with m.Switch(counter):
                def segment(index):
                    return slice(index * wb_bus.granularity, (index + 1) * wb_bus.granularity)

                # First, counter cycles through all the SEL bits to check 
                #   where to expect (read) / send (write) data
                for index, sel_index in enumerate(wb_bus.sel):
                    with m.Case(index):
                        if len(wb_bus.sel) > 1:
                            sel_addr = (
                                int(digit) for digit in format(
                                    index, "0{}b".format(log2_int(len(wb_bus.sel)))
                                )[::-1]
                            )
                        else:
                            sel_addr = ()
                        m.d.comb += csr_bus.addr.eq(Cat(*sel_addr, wb_bus.adr))
                        if index > 0:
                            # CSR reads are registered, and we need to re-register them.
                            m.d.sync += wb_bus.dat_r[segment(index - 1)].eq(csr_bus.r_data)
                        m.d.comb += csr_bus.r_stb.eq(sel_index & ~wb_bus.we)
                        m.d.comb += csr_bus.w_data.eq(wb_bus.dat_w[segment(index)])
                        m.d.comb += csr_bus.w_stb.eq(sel_index & wb_bus.we)
                        m.d.sync += counter.eq(index + 1)

                # After the last chunk is checked, for reads put the last chunk
                #   from CSR bus to Wishbone bus; 
                #   and send ACK to Wishbone bus
                with m.Case(len(wb_bus.sel)):
                    m.d.sync += wb_bus.dat_r[segment(index)].eq(csr_bus.r_data)
                    m.d.sync += wb_bus.ack.eq(1)
                    m.d.sync += counter.eq(len(wb_bus.sel) + 1)

        # Reset counter value only when CYC and STB are no longer asserted at the same time
        with m.Else():
            m.d.sync += counter.eq(0)

        # Ensure ACK is only asserted for 1 clock
        with m.If(wb_bus.ack):
            m.d.sync += wb_bus.ack.eq(0)

        return m
