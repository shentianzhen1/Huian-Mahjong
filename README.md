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

- 校验 144 张实体牌、普通结构胡拆解、金牌限制和所有合法吃牌方案。
- 确定性执行发牌、补花、吃、碰、PASS、头摸、已确认杠后尾摸、普通胡声明和 16 张流局。
- 补杠专用响应窗口、PASS后尾摸及抢杠胡来源审计；相关计分继续明确停止为UNKNOWN。
- 审计已观察的平胡/自摸结算；固定种子重放开局并在未知规则处停止。
- 用 simulation-only 普通局模式验证完整摸打和终局；运行 RandomAgent / BaselineAgent 批量对战与交换座位评估，保留每步决策理由。操作见 [Simulator说明](workspace/simulator/README.md)。
- Recorder V0.2 录制对局；Vision V0.1 对固定 ROI 离线抽帧、标注和模板推理。

## 当前不能做什么

- 真实规则路径仍受抢金、游金链、明暗杠抢杠范围、补杠/抢杠/杠胡计分等 UNKNOWN 限制；普通局模拟奖励不能代表真实最终计分。
- 没有EV决策、特殊胡AI策略或整桌实时识别。
- Executor 未接入，项目不会自动点击小程序。

## 架构

| 层 | 责任 | 状态 |
| --- | --- | --- |
| Rules | 合法性、胡牌结构、番项、结算 | 仅实现已确认部分 |
| Environment | GameState 与可复现状态转移 | M2 可用 |
| Simulator | Agent 驱动牌局 | 普通局闭环、批量评估；特殊规则UNKNOWN |
| AI | 选择合法动作与风险评估 | 可解释Baseline与Random对战；尚无风险模型 |
| Vision | 画面转局面观察 | V0.1 离线 ROI 原型 |
| Executor | 验证通过后执行界面操作 | 未接入 |

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
