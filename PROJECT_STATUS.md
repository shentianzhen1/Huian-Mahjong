# PROJECT_STATUS — Current Snapshot

**Snapshot date:** 2026-10-04
**Execution truth:** [GitHub Issues](https://github.com/shentianzhen1/Huian-Mahjong/issues)
**Rule truth:** `RULE_STATUS.md`；`RULE_EVIDENCE_MATRIX.md` 记录证据与缺口。

## Integrated Status

| Area | Current status |
| --- | --- |
| Rules / Environment | 普通结算、杠胡 / 暗杠胡及抢杠胡自动结算已接通；#4 已于 2026-10-03 关闭，PR #124 / #125 已合并。抢金、三金倒真实终局、八花游仍有证据缺口。 |
| Match | 双人8局、1000/1000开局、零和；正常庄位与连庄底流程保持。 |
| AI | CurrentAgent = MeldAwareShantenAgent V0.10；V0.6 主对照、V0.3 消融。#4 的关闭不代表新策略晋级，后续工作以 #6 当前要求为准。 |
| Vision | Runtime Vision V0.2 experimental/read-only；#7 的冻结独立晋级门仍未通过。旧来源开发结果不作为独立泛化证据。 |
| Current-state advisory | #69：已将开发分支 bad588ef 的 snapshot、结构向听、人工录牌与只读实时桥接集成到本地 Hint UI；实验开关下仅可信输入显示候选弃牌，完整 V0.10 合法动作建议仍待接入。 |
| Hint / Executor | Hint Alpha internal/read-only；Executor off，safe_for_executor=false。 |

## Recent Confirmed Progress

- #120：杠胡 / 暗杠胡无额外倍率，正常杠番叠加后使用普通自摸 ×2。
- #124：抢杠只针对补杠；被抢补杠不成立，原 PENG 保留，不产生失败补杠番或杠费；普通双人结算 ×2，正常庄位流程。
- #125：observed Rob-Kong 终局结算接通，并补充针对性回归。
- 本工作区已同步 GitHub main `96ee733`。规则快照变化后的 AI 评估须保留新 fingerprint，不合并不同指纹的晋级证据。

## Current Execution

本次逐项核验的开放入口为 #1、#2、#3、#5、#6、#7、#9、#45、#69；完整实时列表以 GitHub 为准。

- #1 / #2 / #5：继续收集直接规则与真实终局证据，UNKNOWN / WORKING 不得进入官方 reward / EV。
- #3 仍开放；其正文引用的 #4 依赖已关闭，需依据现有回归核验验收，不自动视为完成。
- #6 仍开放；正文中 #4 未解决的暂停描述已滞后。CurrentAgent 继续 V0.10，后续候选仍须通过即时牌效门及直接对照晋级评估。
- #69：完整可信手牌、Gold、我方副露数可开启结构向听；剩余张数与危险提示还要求完整可信公共牌河及副露身份。约174秒第一局开发检查点不代表其他能力就绪、正式 Vision 晋级或 Executor 安全。
- #7：新 source-disjoint 批次先锁定来源与 truth，再运行冻结 promotion gate；失败后不能反调同一 holdout。

## Regression / Safety Contract

保留144张实体牌守恒、无第5张同牌、最多3张可操作金、非负牌墙、合法动作、死循环检测、双人单局与整场零和、局号单调及同局余牌不增加。CONFIRMED 结算需 focused regression；UNKNOWN stops 不计作流局或胜局。

2026-10-04：离线安装包、人工/实验向听桥、实时观察流水页及独立中文辅助窗口已交付；主界面按用户要求移除录分/证据打点按钮。修复spawn重复UI、后台OCR弹窗和Timeline路径。最终647项unittest通过，独立安装包冒烟通过；这不是识别可用性或正式Vision晋级证据。

**本地实测未通过可用性验收**：用户反馈几乎无法识别、反应缓慢；状态显示手牌/Gold未知、状态栏不可读、M2模板缺失。完整画面诊断和分阶段耗时尚未完成，不能归因于电脑性能或宣称准确率。#45/#69/#7保持开放，完整V0.10合法动作建议未接入。交付清单与限制见 `docs/packaging/2026-10-04_local_test_delivery.md`。

文档入口：`TODO.md` 只索引开放 Issues；`CHANGELOG.md` 只记录历史；执行细节以 GitHub Issues 为准。
