# 惠安麻将助手

以真实对局证据驱动的惠安双人麻将工程。Rules、Environment、Simulator、AI、Vision 与 Executor 分层；UNKNOWN 规则不会被硬编码。

仓库私有：`git clone` 需要已登录且有访问权限的 GitHub 账号。旧名 `Maj` 仍会重定向到现仓库。

## 5 分钟上手

```powershell
git clone https://github.com/shentianzhen1/Huian-Mahjong.git
cd Huian-Mahjong
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -B -m unittest discover -s tests -v
```

可选开发工具：`python -m pip install -e ".[dev]"`。核心测试只依赖 Python 标准库；在仓库根目录直接跑 `unittest` 仍可以。

## 当前能做什么

- Rules：144张实体牌校验、惠安16/17张普通胡拆解、金牌限制、多拆法最高番、全部合法吃牌方案、PENG/杠番及证据感知FanAggregator。
- Environment：确定性执行发牌、补花、吃、碰、PASS、头摸、三类杠后尾摸、补杠专用抢杠窗口、普通胡声明、三金倒一次性窗口、抢金窗口骨架、16张流局。
- Settlement / Match：普通平胡×1、自摸×2使用真实番数和当前庄底结算；8局从1000/1000开始累积零和分数，room541913完整8局fixture可逐局回放到1113/887。
- 庄底：新庄当前结算底10；同一庄家连庄每局+5且不上封顶直到第8局；庄输换庄后新庄重置10。
- Simulator：固定牌墙/seed、交换座位、UNKNOWN证据包、8局真实普通规则MatchRunner，以及统一的整场A/B评估（最终分、分差、点炮、自摸/点炮来源、UNKNOWN）。
- AI：Baseline/Random保留；当前正式前沿仍为 **ShantenAgent V0.3**。现代码标准20 seed×换座40场8局A/B中对Baseline为38胜2负、平均终分1150.75 vs 849.25、平均分差+301.5；点炮12 vs 43。V0.4/V0.5风险启发式均已A/B淘汰。
- Recorder / Vision：Recorder V0.2按局录像；Vision已有固定ROI抽帧、人工标签、模板推理、多帧投票和合法状态约束原型。

## 当前还不能做什么

- 抢金的精确资格/真实结算、三金倒真实终局、游金链完整状态机、抢杠胡完整结算、杠胡倍率、八花游真实倍率仍未全部闭环；详见 [TODO.md](TODO.md) 与 GitHub Issues #1–#5。
- AI已经接通公开8局比赛上下文（当前比分、剩余局数、庄位、庄底、连庄次数）和点炮统计，但还没有通过验证的EV策略。均匀未见牌蒙特卡洛“点炮概率”已校准失败（AUC≈0.499，实际点炮样本平均预测0%），不得使用；当前正在验证明确标记为“非概率”的听牌条件相对风险模型。下一阶段见 Issue #6。
- Vision 尚未建立真实牌面准确率基线；ROI/数据集/稳定性门槛见 Issue #7。
- Executor 未接入。Vision达到量化准确率、置信度和多帧稳定性门槛之前，不启用自动点击。
- 开金实体牌墙记账及少数低频规则（天胡/天听/8局平分）仍保留为P2证据任务。

## 架构

| 层 | 责任 | 当前状态 |
| --- | --- | --- |
| Rules | 合法性、胡牌结构、番项、结算 | 普通规则基本闭环；特殊规则仍有P0缺口 |
| Environment | GameState 与确定性状态转移 | M2可用；特殊窗口逐步补齐 |
| Simulator | 单局/8局、固定牌墙、评估 | ordinary-real 8局可完整运行；特殊结算安全停止 |
| AI | 选择动作、EV与风险 | ShantenAgent V0.3为当前前沿；8局上下文已接通，危险度模型正在校准，尚未形成可晋级EV策略 |
| Vision | 画面转GameState | 离线原型；待真实准确率基线 |
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

Vision 使用单独的 `.venv-capture` 和 OpenCV；CI 只提供手动、非阻断的 advisory job。
评估落盘默认写入 `data/evaluations/`，该目录已忽略，不会进入 Git。

## 文档入口

- [PROJECT_STATUS.md](PROJECT_STATUS.md)：当前能力、问题、测试和进度。
- [RULE_STATUS.md](RULE_STATUS.md)：规则确认等级的唯一真相源。
- [RULE_EVIDENCE_MATRIX.md](RULE_EVIDENCE_MATRIX.md)：规则证据与状态机缺口。
- [TODO.md](TODO.md)：短期工作清单。
- [docs/huian_rules.md](docs/huian_rules.md)：中文规则开发摘要。
- [AGENTS.md](AGENTS.md)：代理改代码前的约束。

修改规则或计分前先更新规则证据；实现存在或测试通过不等于规则已确认。
