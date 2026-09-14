# 项目当前状态

更新日期：2026-09-14（Asia/Shanghai）。本文件只描述当前真实状态；规则证据唯一依据为 [RULE_STATUS.md](RULE_STATUS.md)；实施缺口与录像登记见 [RULE_EVIDENCE_MATRIX.md](RULE_EVIDENCE_MATRIX.md)。实现存在或测试通过不等于规则已确认。

## 当前版本 / 里程碑

- 当前阶段：M2 局中 Environment 已可用；M3 Simulator V0.1 可确定性重放开局并在未知规则处安全停止，尚不能完整模拟一局。
- 最新已核验代码基线：`f324a77`（Record observed Huian outcomes in environment）。本文件自身的提交 SHA 在提交后通过 `git log -1 --format=%H -- PROJECT_STATUS.md CHANGELOG.md` 查询，避免自引用。
- 远程：`https://github.com/shentianzhen1/Maj.git`，分支：`main`。

## 已完成模块

- 通用框架：`mahjong_framework` 提供 Rules、Opening、Settlement 三类玩法插件契约；惠安已实现对应插件，未来玩法可复用 Environment、Simulator、Vision 与 Executor 边界。
- Rules：144 张实体牌校验、普通结构胡听、金牌不能参与吃碰杠、单金平胡房间配置、吃碰杠候选与 UNKNOWN 阻断。
- Opening：17/16 发牌、庄家优先分轮补花、骰子开金候选规划；`begin_opening()` 将结果写入 Environment，停在 `OPENING_QIANGJIN_CHECK`。
- Environment：144 张实体牌守恒、吃碰、PASS、头摸、已解决杠后尾摸、开局及中途补花、16 张零分流局、原子提交、回滚/克隆、死循环保护和合法动作检查。
- 已观察结算：`HuianObservedSettlementPlugin` 仅支持录屏已证实的 `PINGHU`（×1）和 `ZIMO`（×2）。`finalize_observed_outcome()` 可写入由录屏或 Vision 已确认的终局，保留 `END_HAND` 审计事件；不会自动判胡或算番。
- Simulator V0.1：固定种子生成牌墙并重放开局，返回种子、骰子、事件、状态哈希、阶段、牌墙数及 UNKNOWN 列表。抢金核验处安全停止。
- Vision 采集：WGC / PrintWindow / 屏幕区域、PNG/AVI 与元数据、黑屏/停帧/尺寸变化保护。昨日录屏的关键帧已归档在 [capture review](references/capture_review/2026-09-13/README.md)。

## 已确认流程与证据边界

- 当前目标房：2 人、8 局、勾选单金不平胡、无托管。
- PASS 后下一家摸牌；牌墙到 16 张触发 `[0, 0]` 流局。
- 对手打出的当前金牌不可吃、碰、杠或胡。
- 抢金检查位于补花与开金完成后、庄家首打前；三张或以上单金时三金倒优先。完整胡型、席位优先级和结算仍未知。
- 多张真实结算页支持已观察的普通平胡/自摸公式：`(当前庄家底 + 赢家番数) × 胡牌倍率`。该结论不能扩展到抢金、三金倒、游金或杠分。

## 当前测试结果

2026-09-14 全量自动测试：**102 项通过，0 失败，0 跳过**。

| 工作目录 | 命令 | 结果 |
|---|---|---:|
| 项目根目录 | `python -B -m unittest discover -s tests -v` | 75 通过 |
| `legacy_code/core_v0.1.1` | `python -B -m unittest discover -s tests -v` | 9 通过 |
| `legacy_code/environment_v0.1` | `python -B -m unittest discover -s tests -v` | 9 通过 |
| 项目根目录 | `.venv-capture\Scripts\python.exe -B -m unittest workspace.vision.capture_validator.test_capture -v` | 9 通过 |

覆盖固定种子复现、144 张守恒、第五张牌拒绝、非法动作拒绝、16 张流局零和、开局回放、观察结算、回滚、死循环、legacy 基线及 AVI/PNG 编解码。没有完整小程序自动对局端到端测试，也没有 AI 对战评估。

## 已知问题 / 安全停止点

1. 开金候选的骰子定位与补花流程已实现，但翻出的金牌在真实牌墙中的精确实体归属仍未确认；当前 Environment 保留候选牌在墙内，录屏显示开金时可摸牌墙计数会变化，二者尚未完全对齐。
2. 中途摸花与杠后摸花已接入庄家优先补花轮；该流程基于高置信规则，仍需更多实局录像覆盖翻花、墙边界和双人时序。
3. 普通胡牌的实际声明、赢家番数自动聚合、点炮/自摸事件判定尚未接入。观察结算入口只接受外部已确认数据。
4. 抢金、三金倒、游金链、抢杠、加杠细节、杠分与流局杠分均未实现，保持 UNKNOWN。
5. Simulator 不能越过抢金核验点，尚无完整动作循环、批量统计、交换座位评估或 AI。
6. `HuianOnlineRoomV01` 的动态留牌开关是隔离的工作假设，不能覆盖 `RULE_STATUS.md` 的已确认规则。
7. Vision 尚未识别牌面、按钮或结算字段；Executor 尚未接入任何自动点击。

## 下一步计划

1. 用专门录制核验开金翻牌实体归属、抢金胡型/优先级/结算与三金倒时序。
2. 将中途补花接入 Environment，并为真实录像增加状态转移回归用例。
3. 在普通胡牌宣告与番项来源确认后，接入自动结算并让 Simulator 推进完整循环。
4. 完成基础 AI 与可复现批量评估后，再接入 Vision 状态识别和安全 Executor。

## 维护约定

每轮开发完成后：运行上述全量测试；按真实结果更新本文件与 CHANGELOG；检查差异后 commit；push 后检查远程分支状态。规则变化先更新 RULE_STATUS 与证据，未知项不得静默硬编码。