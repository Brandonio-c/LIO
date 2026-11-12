"""Independent verifier for LIO composition records (spec LIO-SW-COMP-001 §6).

Must not import lio or lio_comp. Dependencies: standard library, lxml, jsonschema, lark.
No solver: bound certificates are checked with Fraction arithmetic (z3 is never imported;
tested).
"""

__version__ = "0.1.0"
