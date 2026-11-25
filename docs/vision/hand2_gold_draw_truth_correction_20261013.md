# Hand-2 Gold/draw diagnosis and truth correction — 2026-10-13

Local metadata, no production changes. This supersedes the draw-M3 interpretation
in the preceding Hand-2 short-count review. Sequential source ordinal 3336 has
two black rank strokes on its detached draw: **M2**, not M3. Direct enlarged
primary/tight/normalized crop review found the manual truth error. The immutable
old private truth file is retained and a versioned corrected file records the
change and previous truth digest.

Corrected truth digest:
`fb4fe01d3b5cedad8c600e62c0a9a96d55409e8dd7e3d6c3b1b16a841094082b`.
Only the 3336 draw identity changed. First two scored windows and their 21/31
accepted result are unchanged; 3336 was alignment-blocked in the original
exports, so their valid metric denominator does not change.

The corrected-geometry primary diagnostic remains six correct accepts/eight
truth tiles, zero wrong accepts, with Gold E and draw M2 rejected. The primary
draw candidate M5 at 0.770405 is wrong and rejected. Tight draw candidate M2 at
0.805096 is now correctly interpreted as a correct raw candidate below 0.82,
not a wrong M3-to-M2 confusion. No confidence or acceptance behavior changed.

Gold E is raw top-1 E at 0.653774. The winning E template's exact source is
`94960e642f407502278c66c8f954f062c58f3f43b5d6ce545d8c938efdd32919`.
The candidate bank has two E labels and **zero gold_skin_only E examples**;
`E not in gold_skin_covered`. Thus even an improved above-threshold E appearance
would still require an actual reviewed real-yellow E sample under the existing
Gold-skin support gate. Synthetic recolouring is not a real Gold example, and
the evaluated new-match pixels must not be silently added as holdout support.

The diagnostic ranking helper now exposes the original Gold-normalized template
comparison without changing Runtime. Ordinary ranking is unchanged. Three
focused tests pass including inclusion of real-Gold-only rows in Gold diagnostic
mode and symmetric query/reference features. Embedded missing match_group fields
in ranking rows are not proof of UNKNOWN lineage; the external source registry
must be consulted before any independence claim.

Next: recover genuine old-source Gold E appearance/support with explicit source
lineage, and inspect the corrected M2 query against existing exact Sep-26 M2
support. Preserve threshold 0.82 and the original identity gates. The drawn tile
truth must be corrected before further class-targeted experiments. No advice,
Runtime promotion or Executor permission is granted by this diagnosis.
