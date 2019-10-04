from nmigen import *

from nmigen_soc import csr_bus, wishbone


__all__ = ["WishboneCSR"]


class WishboneCSR(Elaboratable):
    """
    """

    def __init__(self, bus_wb=None, bus_csr=None):
        if bus_wb is None:
            bus_wb = wishbone.Interface()
        self.wb_bus = bus_wb
        if bus_csr is None:
            bus_csr = csr_bus.Interface(datwidth=32, adrwidth=32)
        self.csr_bus = bus_csr

    def elaborate(self, platform):
        m = Module()
        #
        m.d.sync += self.wb_bus.sel.eq(self.wb_bus.sel)
        #
        m.d.sync += [
            self.csr_bus.re.eq(0),                    # FANIN
            self.csr_bus.we.eq(0),                    # FANIN
            self.csr_bus.adr.eq(self.wb_bus.adr),     # FANIN
            self.wb_bus.dat_r.eq(self.csr_bus.dat_r), # FANOUT
            self.csr_bus.dat_w.eq(self.wb_bus.dat_w)  # FANIN
        ]
        # 
        m.submodules += Timeline(
            self.wb_bus.cyc & self.wb_bus.stb, [
                (1, [self.csr_bus.re.eq(~self.wb_bus.we),
                     self.csr_bus.we.eq(self.wb_bus.we)]),
                (2, [self.wb_bus.ack.eq(1)]),
                (3, [self.wb_bus.ack.eq(0)])
            ]
        )
        return m
        

class Timeline(Elaboratable):
    """
    """

    def __init__(self, trigger, events):
        self.trigger = trigger
        self.events = dict()
        if isinstance(events, dict):
            self.events = events
        elif isinstance(events, list):
            for e in events:
                if isinstance(e, tuple) and len(e) == 2:
                    if not isinstance(e[0], int) or not (isinstance(e[1], int) or isinstance(e[1], list)):
                        raise TypeError("{!r} is not a valid enum tuple: should be (index, stmt) or (index, list_of_stmts)"
                                        .format(e))
                    if e[0] < 1:
                        raise ValueError("{!r} must have an index of at least 1"
                                         .format(e))
                    self.events[e[0]] = e[1]
        else:
            raise TypeError("{!r} is not a dict or list"
                            .format(events))
        # Find the maximum event index
        self.evcount = max(self.events)
        # Define a counter that depends on the trigger and timing
        self.counter = Signal(max=self.evcount+1)

    def elaborate(self, platform):
        m = Module()
        # If counter is not 0, increment counter for every clock cycle
        with m.If(self.counter):
            m.d.sync += self.counter.eq(self.counter+1)
        # Otherwise, when trigger asserts, roll back counter to 1
        with m.Elif(self.trigger):
            m.d.sync += self.counter.eq(1)
        # If counter has reached max, reset it back to zero
        with m.If(self.counter == self.evcount + 1):
            m.d.sync += self.counter.eq(0)
        # Append sync statements
        for ind in self.events:
            with m.If(self.counter == ind):
                m.d.sync += self.events[ind]
        return m


# DEBUG
if __name__ == "__main__":
    cbusconv = WishboneCSR()

    from nmigen.back import pysim
    import random

    p = [cbusconv.wb_bus.sel, cbusconv.wb_bus.cyc, cbusconv.wb_bus.stb, cbusconv.wb_bus.ack]
    sync_period = 1e-6
    vcdf = open("_test_csr_busconv.vcd", "w")
    gtkw = open("_test_csr_busconv.gtkw", "w")

    with pysim.Simulator(cbusconv,
                vcd_file=vcdf,
                gtkw_file=gtkw,
                traces=p) as sim:

        def testbench_hello(cbusconv):
            yield from cbusconv.wb_bus.write(0x00, 0)
            yield from cbusconv.wb_bus.write(0x00, 0)
            yield from cbusconv.wb_bus.read(0x00)
            yield from cbusconv.wb_bus.read(0x00)

        sim.add_clock(sync_period)
        sim.add_sync_process(testbench_hello(cbusconv))

        clks = 40

        sim.run_until(sync_period * clks, run_passive=True)
