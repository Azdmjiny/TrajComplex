# Vectoring

- [main/](main/README.md): repaired 20-second evidence-matching result, 26
  candidates; same four scenes and 157 backgrounds. The Encoder cadence is 10 s.
- [controls/](controls/README.md): earlier 10/15/20-second evidence-matching comparison.
- [history/](history/README.md): earlier 5 km screening/evaluation, fixed-scale
  diagnoses, and the original 19-candidate 15 km study.
- [code/](code/README.md): current geometry, certification, input, fitting and
  screening modules plus regression tests.

The smooth-shape comparator is kept inside the same main package as segmented:
their assignments and paired comparisons are shared. Separating their files
would obscure that pairing. Both signs and every failed estimate remain visible.
