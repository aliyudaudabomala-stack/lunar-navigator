"""Scientific computation core for Lunar Navigator.

Everything in this package is deterministic, offline and unit-testable. The
modules implement published algorithms (Meeus, *Astronomical Algorithms*, 2nd
ed.; IAU WGCCRE lunar orientation) rather than calling a remote service, so the
results are reproducible and the provenance of every number is explicit.
"""
