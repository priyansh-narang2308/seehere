"""Benchmark and evaluation (Task 30): annotated items, system outputs, metrics.

Every result row carries an evidence label:
- OBSERVED: the system really ran on this item and its output was measured;
- SIMULATED: computed under a stated assumption (for example, a reviewer who approves every
  held description), never run end to end;
- UNAVAILABLE: the system could not run here (the reason is given). No numbers are invented.
"""
