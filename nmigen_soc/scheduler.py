from nmigen import *


__all__ = ["RoundRobin"]


class RoundRobin(Elaboratable):
    """A round-robin scheduler.

    Parameters
    ----------
    n : int
        Maximum number of requests to handle.

    Attributes
    ----------
    request : Signal(n)
        Signal where a '1' on the i-th bit represents an incoming request from the i-th device.
    grant : Signal(range(n))
        Signal that equals to the index of the device which is currently granted access.
    """
    def __init__(self, n):
        self.n = n
        self.request = Signal(n)
        self.grant = Signal(range(n))

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.grant):
            for i in range(self.n):
                with m.Case(i):
                    with m.If(~self.request[i]):
                        for j in reversed(range(i+1, i+self.n)):
                            t = j % self.n
                            with m.If(self.request[t]):
                                m.d.sync += self.grant.eq(t)

        return m