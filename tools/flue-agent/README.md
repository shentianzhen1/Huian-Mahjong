# Huian-Mahjong Flue persistent development agent

This folder adds a **development-only Flue agent** to the Huian-Mahjong repository. It does not enter the Python package, Vision runtime, Hint Alpha runtime, or Executor.

Its purpose is to keep engineering context across sessions while still treating the repository and GitHub Issues as the source of truth.

## What it gives you

- A persistent conversation keyed by Flue `--id`.
- A file-backed SQLite store at `tools/flue-agent/.flue-data/huian-agent.db`.
- Direct access to the checked-out repository through Flue's trusted local sandbox (`read`, `write`, `edit`, `grep`, `glob`, `bash`).
- Automatic workspace context from the repository root, including `AGENTS.md`.
- A `save_project_checkpoint` tool that stores the last verified ref, completed work, next step, and blockers.
- Project-specific safety instructions: UNKNOWN stays UNKNOWN, no threshold lowering to force acceptance, Hint Alpha remains read-only, and Executor remains off unless repository truth changes.

## Requirements

- Node.js **22.19.0 or newer**.
- An API key for the model provider you choose (for example `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`).
- Recommended for live GitHub inspection: GitHub CLI (`gh`) already authenticated on the machine.

## First-time setup on Windows

From the repository root:

```powershell
cd tools\flue-agent
node --version
npm install
Copy-Item .env.example .env
notepad .env
```

Put your provider key in `.env`. The default model is the documented Flue example `openai/gpt-5.5`; change `FLUE_MODEL` if you want another model supported by Flue.

If `node --version` is below `v22.19.0`, update Node.js first.

Optional GitHub check:

```powershell
gh auth status
```

## Start the persistent Mahjong development agent

Use **one stable ID** for this project:

```powershell
npm run agent -- --id huian-mahjong --message "先读 AGENTS.md，核对 git/GitHub 最新状态，然后告诉我当前最小可验证下一步；先不要提交。"
```

Later, continue the same context with the same ID:

```powershell
npm run agent -- --id huian-mahjong --message "继续上次工作。先检查 checkpoint、git status 和相关 Issue/PR，再完成当前最小可验证下一步。"
```

The second command reuses the same Flue conversation and SQLite-backed project checkpoint instead of starting from zero.

## Recommended workflow for this repository

1. Keep normal development in the existing Python repository.
2. Start Flue with `--id huian-mahjong`.
3. Ask it to verify the current branch, Issue, PR and tests before editing.
4. Let it make one bounded local change and run tests.
5. Review `git diff` yourself (or with Codex/ChatGPT) before asking it to commit/push.
6. Keep PR merging manual unless you explicitly decide otherwise.

Useful prompts:

```text
读取最新 main、Open Issues、Open PR 和 PR #117。GitHub 是真源。只做审计，不修改。
```

```text
继续 Issue #69。只完成一个最小可验证下一步，不能降低阈值，UNKNOWN 保持 UNKNOWN，Executor 关闭。完成后跑相关测试并保存 checkpoint。
```

```text
检查上次 checkpoint 是否已经被 GitHub 新提交淘汰；如果过期，以 GitHub 为准并更新 checkpoint。
```

## Choosing a different model

Edit `.env`, for example:

```dotenv
FLUE_MODEL=anthropic/claude-sonnet-4-6
ANTHROPIC_API_KEY=your-key-here
```

Do not commit `.env`.

## Context reset vs. continuation

- Continue the project: keep using `--id huian-mahjong`.
- Start an isolated experiment: use a different ID, for example `--id huian-vision-experiment`.
- The agent must still re-check repository/GitHub state; persistent context is a convenience, not a replacement for source-of-truth verification.

## Security note

Flue's `local()` sandbox is **not isolated**: it uses the real filesystem and shell. Use it only on a trusted checkout and do not feed it untrusted instructions. This integration deliberately does not copy the full host environment into the model's shell.
