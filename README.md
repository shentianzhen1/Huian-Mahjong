# 惠安麻将助手

以真实对局证据驱动的惠安双人麻将工程。Rules、Environment、Simulator、AI、Vision 与 Executor 分层；UNKNOWN 规则不会被硬编码。

仓库当前为公开仓库，可直接 `git clone`。旧名 `Maj` 仍会重定向到现仓库。

当前内测开发位于 **Draft PR #126** 的 `codex/hint-alpha-local-test-sync-20261004` 分支，未合并、未正式推广。近期目标是完整手牌＋开金＋我方副露数量可信后提供只读结构向听建议；开发候选、当前安装版、独立对局验收是三件不同的事。总体快照见 [PROJECT_STATUS.md](PROJECT_STATUS.md)，审计见 [本轮项目审计](docs/project_audit_20261018.md)。

## 5 分钟上手

```powershell
git clone https://github.com/shentianzhen1/Huian-Mahjong.git
cd Huian-Mahjong
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e . pytest
python -B -m pytest -q tests
```

可选开发工具：`python -m pip install -e ".[dev]"`。Vision 使用 `python -m pip install -e ".[vision]"`。`pytest` 会收集函数式测试和 unittest；只运行标准库 `unittest` 是较小的测试子集，不应报告为完整 CI 回归。

Linux / macOS：

```bash
git clone https://github.com/shentianzhen1/Huian-Mahjong.git
cd Huian-Mahjong
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e . pytest
python -B -m pytest -q tests
```

## 当前能做什么

- Rules：144张实体牌校验、惠安16/17张普通胡拆解、金牌限制、多拆法最高番、全部合法吃牌方案、PENG/杠番及证据感知FanAggregator。
- Environment：确定性执行发牌、补花、吃、碰、PASS、头摸、三类杠后尾摸、补杠专用抢杠窗口、普通胡声明、三金倒可重复后续提示窗口、抢金窗口骨架、16张流局。
- Settlement / Match：普通平胡×1、自摸×2使用真实番数和当前庄底结算；8局从1000/1000开始累积零和分数，match_evidence_001完整8局fixture可逐局回放到1113/887。
- 庄底：新庄当前结算底10；同一庄家连庄每局+5且不上封顶直到第8局；庄输换庄后新庄重置10。
- Simulator：固定牌墙/seed、交换座位、UNKNOWN证据包、8局真实普通规则MatchRunner，以及统一的整场A/B评估（最终分、分差、点炮、自摸/点炮来源、UNKNOWN）。
- AI：当前正式前沿为 **`CurrentAgent = MeldAwareShantenAgent V0.10`**；`TenpaiRiskTieBreakAgent V0.6` 保留为固定主对照，`ShantenAgent V0.3` 保留为牌效消融基线。V0.10继承V0.6弃牌策略，只在CHI/PENG窗口比较PASS与副露后的最优强制弃牌，并且只有普通进攻元组严格改善时才副露。两批独立评估合计200个seed pair / 400场完整8局：V0.10为239胜、V0.6为159胜、2平，平均配对最终分差+54.805。KONG已接入只读影子审计，显式标注抢杠/杠胡未知项，不改变当前策略。新策略必须使用固定牌墙+正反换座+Agent身份稳定RNG，直接击败V0.10才能晋级。
- Recorder / Vision：按局录像、动态牌面几何、手牌/摸牌/开金读取，以及比分/局数/剩余牌的多帧融合与物理约束。旧版小样本离线高分不是当前完整手牌或实时准确率；当前 Runtime 门槛固定0.82。开发补充模板、紧裁图回退和牌缝原型尚未接入安装版，独立对局与 Windows 投屏验收仍待完成。指标边界见 [快照](PROJECT_STATUS.md) 与 [候选恢复说明](docs/vision/private_candidate_desktop_restore_20261017.md)。

## 当前状态建议与离线流水（Issues #69/#45）

当前 Draft 集成包含 HandTimeline/中文 Match Ledger、public river/meld observer、Runtime Vision bridge、Temporal Action Assembler、公共牌几何检测与跨帧追踪、Hand Context、庄家标记和 Player Perspective V0.1。这不代表整个 Draft PR 已合并到 main。新来源没有证据时仍保持 UNKNOWN。

**这还不是完整真实对局自动识别。** 当前优先完整手牌、开金和自动检测路径的副露数量/身份；逐帧完整转录八局不是基础向听建议的前置条件。副露身份未确认时保持 UNKNOWN；只有自身输入完整时才允许结构向听，缺公共身份则继续关闭余张和危险提示。正式 Vision 晋级仍须通过 Issue #7 的独立盲测；Hint Alpha 只读，Executor 关闭。

开发顺序、证据检查与 PR 验收说明见 [开发与证据流程](docs/development_workflow.md)。

## 当前还不能做什么

- 玩家已确认的规则事实与端到端实现必须分开：普通杠后自摸、暗杠后自摸和补杠抢胡计分已有确认与回归；三金倒/八花及部分开局规则有分阶段API，但抢金、天听、持续提示等完整模拟/实时接线仍有迁移缺口。具体以 [RULE_STATUS.md](RULE_STATUS.md) 与执行 Issues 为准，不把未接线写成规则未知。
- CurrentAgent 冻结在 V0.10；离线模拟上下文不等于已接入实时 UI。既有关闭的 Agent 实验不会因文档建议自动重启，当前识别工作不升级策略版本。
- Vision 的现有模板类别覆盖不等于来源独立和整手可用。仍需独立原始对局、完整手牌、更多draw连续序列、状态栏时点、缩放/移动/遮挡压力测试及真实 Windows 采集验收；见 Issue #7。
- Executor 未接入。Vision达到量化准确率、置信度和多帧稳定性门槛之前，不启用自动点击。
- 开金实体牌墙记账已解决：开出的金固定占1张实体牌且不可再摸，可操作金最多3张。P2仅剩少数低频规则（天胡/天听/8局平分等）。

## 架构

| 层 | 责任 | 当前状态 |
| --- | --- | --- |
| Rules | 合法性、胡牌结构、番项、结算 | 普通结算已回归；特殊规则事实与迁移进度分开记录 |
| Environment | GameState 与确定性状态转移 | M2可用；特殊窗口逐步补齐 |
| Simulator | 单局/8局、固定牌墙、评估 | ordinary-real 8局可完整运行；特殊结算安全停止 |
| AI | 选择动作、EV与风险 | V0.10冻结；V0.6固定主对照，V0.3消融基线；不等于实时策略接线完成 |
| Vision | 画面转观察 | Runtime与开发候选分离；独立对局、整手及实时采集仍未验收 |
| Executor | UI执行 | 未接入，等待Vision门槛 |

## 版本与评估身份

这几个版本号含义不同，不互相替代：

- Project package：当前 Draft 分支打包身份为 `0.2.1`；不据此宣称 main 已发布该版本。
- RuleSnapshot：用 SHA-256 fingerprint 标识精确规则证据快照；规则变化时 fingerprint 变化。
- Agent：当前正式策略 `MeldAwareShantenAgent V0.10`，独立于项目 release。
- Vision：Runtime Vision V0.2 是视觉子系统版本，目前仍是 experimental/read-only，不等同项目 release。

保存型 Simulator 评估会同时记录 project、rule snapshot、agent provenance、Python runtime 与 runtime source digest；冻结的 `legacy_code/` 不再计入运行时代码指纹。

## 测试

核心回归（GitHub Actions 当前在 Python 3.10–3.14 执行；纯文档改动除外）：

```powershell
python -B -m pytest -q tests
```

完整本地回归：

```powershell
python -B -m pytest -q tests
Push-Location legacy_code\core_v0.1.1; python -B -m unittest discover -s tests -v; Pop-Location
Push-Location legacy_code\environment_v0.1; python -B -m unittest discover -s tests -v; Pop-Location
.\.venv-capture\Scripts\python.exe -B -m unittest workspace.vision.capture_validator.test_capture -v
.\.venv-capture\Scripts\python.exe -B -m unittest workspace.vision.tiles_v0_1.test_tiles_v0_1 -v
```

Vision 使用 OpenCV/Pillow；`.github/workflows/vision-tests.yml` 会在 `workspace/vision/**` 或 `dataset/tiles_v0_1/**` 变更时自动运行独立 Vision Regression。核心 `tests.yml` 不再重复维护第二套手动 Vision job。
评估落盘默认写入 `data/evaluations/`，该目录已忽略，不会进入 Git。

## 文档入口

推荐阅读顺序：执行任务先看 GitHub Issues / [TODO.md](TODO.md)，规则事实只看 [RULE_STATUS.md](RULE_STATUS.md) 与相关证据；需要总体快照再看 [PROJECT_STATUS.md](PROJECT_STATUS.md)。[CHANGELOG.md](CHANGELOG.md) 只用于追历史，不应作为当前状态真相源。

- [PROJECT_STATUS.md](PROJECT_STATUS.md)：一页当前集成快照，不复制执行 backlog。
- [docs/packaging/BOUNDARY.md](docs/packaging/BOUNDARY.md)：当前 wheel 内容边界与后续拆包迁移顺序。
- [docs/packaging/DEPENDENCY_GRAPH.md](docs/packaging/DEPENDENCY_GRAPH.md)：拆包前强制依赖方向（core → AI/Vision → Simulator/Hint）。
- [RULE_STATUS.md](RULE_STATUS.md)：规则确认等级的唯一真相源。
- [RULE_EVIDENCE_MATRIX.md](RULE_EVIDENCE_MATRIX.md)：规则证据与状态机缺口。
- [TODO.md](TODO.md)：Open GitHub Issues 的入口索引，不承载独立状态。
- [docs/huian_rules.md](docs/huian_rules.md)：中文规则开发摘要。
- [AGENTS.md](AGENTS.md)：代理改代码前的约束。
- [docs/rule_isolation.md](docs/rule_isolation.md)：规则版本隔离、RuleSnapshot、AI评估防污染与规则纠错流程。

安装包运行时兼容代码位于 `huian/_compat/`；`legacy_code/` 仅保留冻结历史基线与 advisory 对照测试，不再作为 setuptools 安装来源。

修改规则或计分前先更新规则证据；实现存在或测试通过不等于规则已确认。
