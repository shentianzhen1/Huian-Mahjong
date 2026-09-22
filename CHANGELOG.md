# 重要变更记录

本文件只保留最近变更。旧记录按日期归档，避免根目录历史日志与当前状态源互相干扰。

## 历史归档

- [2026-09-20](docs/changelog/2026-09-20.md)
- [2026-09-19](docs/changelog/2026-09-19.md)
- [2026-09-18](docs/changelog/2026-09-18.md)
- [2026-09-15](docs/changelog/2026-09-15.md)

## 2026-09-22 — Hint Alpha 本地 Doctor 与安装自检

- 新增 `workspace.hint_alpha.doctor` 与 `CHECK_HINT_ALPHA.bat`，分开报告 Demo、Live Capture、PublicState OCR 三层 readiness；Executor 固定 OFF。
- 安装脚本不再只依赖 `py -3.11`，会在 Python 3.10–3.14 中寻找可用解释器；依赖安装完成后自动执行 live-capture Doctor。
- Tesseract 继续是可选项：缺失时只警告 PublicState OCR unavailable，不阻止采集、录像和证据记录。
- Hint Alpha evidence session、录像 metadata 与 UI 版本栏补齐 project release 0.2.0，与 RuleSnapshot fingerprint 和 CurrentAgent V0.10 分开记录。
- 启动失败时 `START_HINT_ALPHA.bat` 明确提示先运行自检，不再只有“一闪而过”的失败体验。

## 2026-09-22 — PublicState 64时点状态栏审计迁入最新主线

- 从暂停的旧PR #42中只迁移仍有效的证据和窄修复，不整分支合并，避免覆盖后续Runtime Vision V0.2 / PublicState改动。
- 同批8局录像按5/10/15/20/25/30/40/50秒建立64时点审计；remaining有63个可评分点，primary为44/63正确、53/63可读。
- 只在primary无法解析时收窄remaining ROI右缘14%并重试；10个原不可读点全部恢复，达到54/63正确、63/63可读。
- 9个false-valid primary错误继续保留，不让fallback覆盖合法primary，不做字符硬映射；因此本改动改善可读性但不解决可靠性门槛。
- 结果明确为same-batch diagnostics，不用于Runtime Vision V0.2正式晋级；Executor继续关闭。

## 2026-09-22 — Package 0.2.0：版本身份与评估 provenance 收口

- Python package / project release 升至 `0.2.0`，并通过 `huian.__version__` / `PROJECT_VERSION` 暴露；它只表示仓库集成版本，不替代 RuleSnapshot 或 Agent 版本。
- 保存型 Simulator 评估升级为 schema v3，同时记录 project manifest、RuleSnapshot、Agent class/version、Python runtime 与 runtime source digest。
- 8局 paired evaluation 新增 project version 与 agent versions；无法确认版本的自定义/基线 factory 显式记录 `None`，不猜测。
- runtime source digest 不再包含 `legacy_code/`；冻结历史基线仍保留 advisory CI，但修改历史对照代码不会再污染当前评估重放身份。
- 安装包 smoke test 强制校验 setuptools metadata 版本与 `huian.__version__` 一致。
- 本次只收口版本和评估可追溯性，不改变惠安麻将规则、CurrentAgent V0.10策略、Vision阈值或Executor状态。

## 维护方式

每轮重要开发完成且完整测试通过后，追加日期、commit 或可解析的提交引用、新增功能、修复、规则及测试变化，并更新 PROJECT_STATUS 当前快照。无变更的栏目写“无”；未验证的状态明确标注。提交前记录真实测试，提交并 push 后核验远程 HEAD。历史条目保留，只有发现事实错误时作明确更正。
