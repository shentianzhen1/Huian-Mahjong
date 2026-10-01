'use agent';

import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { useModel, usePersistentState, useSandbox, useTool } from '@flue/runtime';
import { local } from '@flue/runtime/node';
import * as v from 'valibot';

const here = dirname(fileURLToPath(import.meta.url));
const packageRoot = resolve(here, '../..');
const defaultRepoRoot = resolve(packageRoot, '../..');

export function HuianMahjongDevAgent() {
  const repoRoot = process.env.HUIAN_REPO_ROOT?.trim() || defaultRepoRoot;
  const model = process.env.FLUE_MODEL?.trim() || 'openai/gpt-5.5';

  useModel(model, {
    thinkingLevel: 'high',
    compaction: { keepRecentTokens: 16000 },
  });

  // This is intentionally a trusted local coding sandbox. It can read/write the
  // real checkout and run tests, but it does not receive a copied process.env.
  useSandbox(local({ cwd: repoRoot }));

  const [checkpoint, setCheckpoint] = usePersistentState('project_checkpoint', {
    verifiedRef: 'not-recorded',
    focus: 'not-recorded',
    completed: 'not-recorded',
    nextStep: 'read AGENTS.md and verify current GitHub/local state',
    blockers: '',
    savedAt: 'not-recorded',
  });

  useTool({
    name: 'save_project_checkpoint',
    description:
      'Persist the verified Huian-Mahjong engineering checkpoint after substantial work so the next conversation can resume without reconstructing context.',
    input: v.object({
      verifiedRef: v.string(),
      focus: v.string(),
      completed: v.string(),
      nextStep: v.string(),
      blockers: v.optional(v.string()),
    }),
    async run(input) {
      const next = {
        verifiedRef: input.verifiedRef,
        focus: input.focus,
        completed: input.completed,
        nextStep: input.nextStep,
        blockers: input.blockers ?? '',
        savedAt: new Date().toISOString(),
      };
      setCheckpoint(next);
      return next;
    },
  });

  return `
You are the persistent development agent for shentianzhen1/Huian-Mahjong.
Your filesystem/shell working directory is the repository root.

Repository operating rules:
1. Read and obey AGENTS.md before changing code. GitHub Issues are the execution truth source; RULE_STATUS.md and RULE_EVIDENCE_MATRIX.md are the Mahjong-rule truth sources.
2. At the start of a task, inspect git status and current branch. When network access is available, fetch/prune origin and verify any referenced GitHub Issue/PR with git/gh before relying on old notes. If live GitHub verification is unavailable, say so and do not invent current state.
3. UNKNOWN stays UNKNOWN. Do not hard-code an unverified Mahjong rule, do not lower a Vision confidence threshold just to make a case pass, and do not convert missing evidence into a default value.
4. Keep Rules / Environment / Simulator / AI / Vision / Executor boundaries intact. Hint Alpha stays read-only unless the repository truth explicitly changes. Executor stays off unless a separately approved safety gate exists.
5. Prefer the smallest verifiable change. Run the relevant tests after code changes and report the exact commands/results.

Git safety:
- Local inspection, editing and tests are allowed.
- Do not commit or push unless the user's current message explicitly asks for it.
- Never force-push.
- Never merge a PR, close an Issue/PR, or modify main directly unless the user's current message explicitly names that action and target.
- Preserve user changes; do not reset or discard unrelated work.

Context discipline:
- Use the same agent id across sessions for continuity.
- Do not treat conversation memory as repository truth when GitHub/local evidence disagrees.
- After substantial verified work, call save_project_checkpoint with a concise verified ref, what was completed, the single next step, and blockers.

Last persisted checkpoint:
${JSON.stringify(checkpoint, null, 2)}
`;
}
