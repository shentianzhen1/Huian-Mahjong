# 惠安麻将助手

以真实对局证据驱动的惠安双人麻将工程。Rules、Environment、Simulator、AI、Vision 与 Executor 分层；UNKNOWN 规则不会被硬编码。

仓库当前为公开仓库，可直接 `git clone`。旧名 `Maj` 仍会重定向到现仓库。

## 5 分钟上手

```powershell
git clone https://github.com/shentianzhen1/Huian-Mahjong.git
cd Huian-Mahjong
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -B -m unittest discover -s tests -v
```

可选开发工具：`python -m pip install -e ".[dev]"`。Vision 使用 `python -m pip install -e ".[vision]"`。核心测试只依赖 Python 标准库；在仓库根目录直接跑 `unittest` 仍可以。

Linux / macOS：

```bash
git clone https://github.com/shentianzhen1/Huian-Mahjong.git
cd Huian-Mahjong
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -B -m unittest discover -s tests -v
```

## 当前能做什么

- Rules：144张实体牌校验、惠安16/17张普通胡拆解、金牌限制、多拆法最高番、全部合法吃牌方案、PENG/杠番及证据感知FanAggregator。
- Environment：确定性执行发牌、补花、吃、碰、PASS、头摸、三类杠后尾摸、补杠专用抢杠窗口、普通胡声明、三金倒一次性窗口、抢金窗口骨架、16张流局。
- Settlement / Match：普通平胡×1、自摸×2使用真实番数和当前庄底结算；8局从1000/1000开始累积零和分数，room541913完整8局fixture可逐局回放到1113/887。
- 庄底：新庄当前结算底10；同一庄家连庄每局+5且不上封顶直到第8局；庄输换庄后新庄重置10。
- Simulator：固定牌墙/seed、交换座位、UNKNOWN证据包、8局真实普通规则MatchRunner，以及统一的整场A/B评估（最终分、分差、点炮、自摸/点炮来源、UNKNOWN）。
- AI：当前正式前沿为 **`CurrentAgent = MeldAwareShantenAgent V0.10`**；`TenpaiRiskTieBreakAgent V0.6` 保留为固定主对照，`ShantenAgent V0.3` 保留为牌效消融基线。V0.10继承V0.6弃牌策略，只在CHI/PENG窗口比较PASS与副露后的最优强制弃牌，并且只有普通进攻元组严格改善时才副露。两批独立评估合计200个seed pair / 400场完整8局：V0.10为239胜、V0.6为159胜、2平，平均配对最终分差+54.805。新策略必须使用固定牌墙+正反换座+Agent身份稳定RNG，直接击败V0.10才能晋级。
- Recorder / Vision：Recorder V0.2按局录像。Vision已用8局真实回放建立严格 `same_region + leave-session-out` 基线；修正1条人工错标后，hand+draw为147/149=**98.66%**，置信度≥0.80的127个样本为127/127正确。Gold V0.1在当前8局196个可检测帧中193帧正确=**98.47%**，8/8局多数票正确，但这仍是同批录像时序结果，不是外部泛化率。PublicState V0.1已实现比分/局数/剩余牌的多帧融合与物理约束。

## 当前还不能做什么

- 抢金的精确资格/真实结算、三金倒真实终局、游金链完整状态机、抢杠胡完整结算、杠胡倍率、八花游真实倍率仍未全部闭环；详见 [TODO.md](TODO.md) 与 GitHub Issues #1–#5。
- AI已经接通公开8局比赛上下文（当前比分、剩余局数、庄位、庄底、连庄次数）和点炮统计。V0.11/V0.12的“排除金等待后再做即时score-aware”路径已验证为结构性几乎不可触发，因此不再沿这条死门槛继续堆版本。下一阶段优先研究有金时的副露/特殊状态EV、KONG决策，以及不依赖该死门槛的多步/整场EV；见 Issue #6。
- Vision 已有真实牌面基线，但仍缺新的独立录屏批次、部分牌类覆盖、更多draw连续序列，以及双方分数/剩余牌数/局数的可靠数字读取器。当前离线高分不等于端到端可用；见 Issue #7。
- Executor 未接入。Vision达到量化准确率、置信度和多帧稳定性门槛之前，不启用自动点击。
- 开金实体牌墙记账及少数低频规则（天胡/天听/8局平分）仍保留为P2证据任务。

## 架构

| 层 | 责任 | 当前状态 |
| --- | --- | --- |
| Rules | 合法性、胡牌结构、番项、结算 | 普通规则基本闭环；特殊规则仍有P0缺口 |
| Environment | GameState 与确定性状态转移 | M2可用；特殊窗口逐步补齐 |
| Simulator | 单局/8局、固定牌墙、评估 | ordinary-real 8局可完整运行；特殊结算安全停止 |
| AI | 选择动作、EV与风险 | CurrentAgent = MeldAwareShantenAgent V0.10；V0.6固定主对照，V0.3消融基线；下一步是有金副露/KONG/多步与整场EV |
| Vision | 画面转GameState | hand+draw严格基线98.66%；Gold当前批次多帧98.47%；PublicState约束层已接，待数字读取器和外部泛化 |
| Executor | UI执行 | 未接入，等待Vision门槛 |

## 测试

核心回归（GitHub Actions 默认在 Python 3.10/3.11/3.12 执行）：

```powershell
python -B -m unittest discover -s tests -v
```

完整本地回归：

```powershell
python -B -m unittest discover -s tests -v
Push-Location legacy_code\core_v0.1.1; python -B -m unittest discover -s tests -v; Pop-Location
Push-Location legacy_code\environment_v0.1; python -B -m unittest discover -s tests -v; Pop-Location
.\.venv-capture\Scripts\python.exe -B -m unittest workspace.vision.capture_validator.test_capture -v
.\.venv-capture\Scripts\python.exe -B -m unittest workspace.vision.tiles_v0_1.test_tiles_v0_1 -v
```

Vision 使用 OpenCV/Pillow；`.github/workflows/vision-tests.yml` 会在 `workspace/vision/**` 或 `dataset/tiles_v0_1/**` 变更时自动运行独立 Vision Regression。核心 `tests.yml` 不再重复维护第二套手动 Vision job。
评估落盘默认写入 `data/evaluations/`，该目录已忽略，不会进入 Git。

## 文档入口

推荐阅读顺序：执行任务先看 GitHub Issues / [TODO.md](TODO.md)，规则事实只看 [RULE_STATUS.md](RULE_STATUS.md) 与相关证据；需要总体快照再看 [PROJECT_STATUS.md](PROJECT_STATUS.md)。[CHANGELOG.md](CHANGELOG.md) 只用于追历史，不应作为当前状态真相源。

- [PROJECT_STATUS.md](PROJECT_STATUS.md)：当前能力、问题、测试和进度摘要。
- [RULE_STATUS.md](RULE_STATUS.md)：规则确认等级的唯一真相源。
- [RULE_EVIDENCE_MATRIX.md](RULE_EVIDENCE_MATRIX.md)：规则证据与状态机缺口。
- [TODO.md](TODO.md)：GitHub Issues 的短期索引/摘要。
- [docs/huian_rules.md](docs/huian_rules.md)：中文规则开发摘要。
- [AGENTS.md](AGENTS.md)：代理改代码前的约束。

修改规则或计分前先更新规则证据；实现存在或测试通过不等于规则已确认。
