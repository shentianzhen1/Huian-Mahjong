# Hand 2 fixed-candidate diagnostic — 2026-10-13

Local record, no export approval or production change. User supplied the exact
Drive recording and identified it as complete Hand 2 without the black band.
The actual three centre frames show 2/8, and all fifteen reviewed hand-region
frames show no black band. No claim that every video frame was inspected.

Source SHA: `05f657c13cc68729ad008796c5672b7156693ad4af011dc82bcd4dbb8d418a19`.
4170 reported frames. Predeclared 20/50/80% ordinals: 834/2085/3336. Sequential
five-frame windows were inspected before classification; centre RGB hashes bind
the locked truth. Truth hash:
`4f5ed1aa5b712b0583260de84ab25f8f9a7f4ac99015a9b0200a4e6d01ac075b`.
Expanded development candidate unchanged from the preceding run; file inventory
hash: `5f0f4ba0b1385a38cb9b40c6968ab34c5df35348716015afcd71d3f05a6a7f6e`.
No support added or parameters tuned after viewing Hand 2.

| Ordinal | Truth hand + draw | Committed baseline correct accepted | Expanded + fallback correct accepted | Wrong accepted | Alignment |
| --- | --- | --- | --- | --- | --- |
| 834 | 16 + 1 | 5/17 | 12/17 | 0 | exact count, crops reviewed |
| 2085 | 13 + 1 | 6/14 | 9/14 | 0 | exact count, crops reviewed |
| 3336 | 7 + 1 | not scored | not scored | not scored | failed region/count alignment |

The aligned identity denominator is 31, not 39. Expanded candidate accepts
21 correct, rejects 10, and has no wrong accepts in those aligned slots. The
eight truth tiles at 3336 are unscored, not eight classifier rejects or successes.
All three snapshots remain incomplete. First window includes raised S1; the
last has Ting badges and three exposed meld groups. Opened Gold reads E by manual
review, but this is not proof that machine Gold acquisition/advice gates passed.

At 3336, actual exported components label all nine left-side exposed-meld faces
as hand and the concealed Gold E as draw_visual. Detector boxes were overlaid
on the exact sequential frame and actually inspected. Thus the defect is a
meld-versus-concealed region swap, not merely two extra concealed boxes. The
real seven-tile hand and detached draw are not correctly assigned. Do not shift
truth into these boxes or count their predicted identities as classifier errors.

For the other windows, all 31 saved primary crops were visually checked and
contain the intended complete faces. Remaining identities include Gold E,
S9, SOUTH, source-supported M8, and one M2. Preserve the 0.82 and source gates.

This Hand 2 belongs to the same uploaded match as the already revealed Hands
3/7. It is a fixed-candidate continuation test, not independent-match promotion.
Next prioritize region separation under multiple exposed groups/Ting overlays
with both count and physical-layout validation. Runtime remains unchanged.
