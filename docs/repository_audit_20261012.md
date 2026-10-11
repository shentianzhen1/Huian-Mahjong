# Repository audit — 2026-10-12

Read-only audit of `shentianzhen1/Huian-Mahjong` as seen from a local clone plus
the GitHub API. No branch, PR, issue or file was modified by this audit.

## Headline

Work is progressing, but **it is not reaching `main`**. `main` has not moved
since 2026-10-03, while the newest active PR head is from 2026-10-12. Every
advance since then sits in draft branches.

## Branches

| measured | value |
| --- | --- |
| remote branches | **116** |
| branches whose PR is already merged, but still present | **82** |
| open PRs | 10 |
| of which draft | **9** |
| merged PRs (all time) | 83 |

82 of 116 branches (71%) belong to merged pull requests and are dead weight.
They make branch listing hard to read and hide the small number of branches that
actually matter.

Branch namespaces in use (`feat` 40, `feature` 17, `fix` 14, `chore` 11,
`docs` 8, plus `evidence`, `experiment`, `eval`, `ci`, `codex`, `integration`):
`feat` and `feature` are both in use for the same purpose, so the same kind of
work appears under two prefixes.

## The open PR stack

Five PRs target `main` independently, and five form a single chain:

```
independent of each other, all base=main
  #117  DRAFT  integration/issue69-replay-stack-20260926
  #121  DRAFT  feat/flue-persistent-dev-agent
  #122  ready  docs/repository-audit-20261003
  #123  DRAFT  rules/close-rob-kong-settlement-20261003
  #126  DRAFT  codex/hint-alpha-local-test-sync-20261004      <- newest, 2026-10-12

one chain, each based on the previous
  #126 -> #127 -> #128 -> #129 -> #130 -> #131
```

Consequences of the chain:

- **Nothing in #127–#131 can merge while #126 is unmerged.** #127 targets #126's
  head, and each later PR targets the previous one's head. The chain's five PRs
  are effectively one unit.
- A review of #131 shows a diff against `sim/tianting-status-routing`, not
  against `main`, so its real change against `main` is not visible from the PR
  page.
- If #126 is abandoned or rebuilt, all five dependents need rebasing.

`#117` is the older Issue #69 integration PR (`38ed6b8`, 2026-10-06) and is
superseded in content by `#126` (`32fdf5b`, 2026-10-12), which is itself based
on `main`. Both being open drafts invites confusion about which is current.

## main is stale

| ref | commit | date |
| --- | --- | --- |
| `main` | `96ee733` | 2026-10-03 |
| `#117` head | `38ed6b8` | 2026-10-06 |
| `#126` head | `32fdf5b` | 2026-10-12 |

Measured locally: against the shallow clone, `origin/main..origin/codex-hint-alpha-sync`
reports one commit, but that figure is meaningless here because the clone is
shallow (`git merge-base` cannot resolve). The reliable statement is the date
gap: **nine days of merged-quality work has not reached the default branch.**

`AGENTS.md` states that GitHub Issues are the only truth source for current
execution work, and `docs/development_workflow.md` describes small-PR flow. A
default branch that is nine days behind undercuts both: a fresh clone does not
contain the current state.

## Documentation drift

`PROJECT_STATUS.md` (snapshot date 2026-10-03) says:

- "Draft PR #117 ... is the active read-only integration branch"

That is no longer accurate. There are now 10 open PRs and the newest activity is
on #126, not #117. The file also states the project release is `0.2.0` in the
README while `pyproject.toml` has carried `0.2.1`.

## Repository metadata

| field | current | note |
| --- | --- | --- |
| license | **none** | README says the repository can be cloned and installed directly; with no licence, reuse rights are undefined |
| description | `Human` | not descriptive; does not say what the project is |
| size | ~11.6 MB | reasonable; private footage is correctly excluded |

## Issues

Nine open issues excluding PRs: `#1`, `#2`, `#3`, `#5`, `#6`, `#7`, `#9`,
`#45`, `#69`. Issue #4 is closed (Rob-Kong settlement, PR #125). Priority
labels are carried in titles (P0/P1) rather than in GitHub labels; the issue
list shows no labels configured.

`#69` has 60 comments and `#6` has 21, which is where the working discussion
lives. `#122` (`docs/repository-audit-20261003`) appears to be a previous
repository-audit PR that is still open and unreviewed.

## Recommended actions, in order

1. **Decide #126.** It blocks five chained PRs and holds the newest work. Either
   merge it to `main` (clearing the nine-day default-branch gap) or split the
   parts that are ready. Nothing else in the backlog unblocks as much.
2. **Retarget or close #117.** Its content is superseded by #126. Leaving two
   Issue #69 integration drafts open makes "which is current" ambiguous.
3. **Delete the 82 merged branches.** They are unambiguous: the PR is merged, so
   the branch carries no unique work. Enabling "automatically delete head
   branches" on the repository prevents recurrence.
4. **Update `PROJECT_STATUS.md`** to name #126 as the active branch and to stop
   calling #117 active; fix the `0.2.0`/`0.2.1` drift.
5. **Add a licence.** Without one the "clone and install" instruction in the
   README grants nothing.
6. **Replace the repository description** with a one-line summary.
7. **Label the open issues** with their P0/P1 priority instead of encoding it in
   the title, so the backlog can be filtered.

Items 3 to 7 are mechanical and low-risk. Items 1 and 2 are decisions only the
repository owner can make, and they are the ones that matter.

## Boundaries

This audit changed nothing: no branch deleted, no PR touched, no file edited in
the repository, no issue commented. It reads public API responses and the local
clone only. Numbers are as observed on 2026-10-12.
