# 私有开发素材接入

本工具落实 Issue [#69](https://github.com/shentianzhen1/Huian-Mahjong/issues/69) 的来源恢复与分组要求。它验证私有文件身份、生成不含文件路径的开发清单，并审计来源覆盖；不是 Runtime 模板加载器，也不代表识别算法已晋级。

## 已补入的项目能力

`workspace.vision.development_asset_intake` 提供：

- `client_tile_to_project()`：显式转换客户端“筒、条、万”的数字编码，拒绝负值、布尔值、未知编号；花牌与34类标准牌分开。
- `build_intake()`：验证42种包牌面及其图集/元数据哈希，恢复裁图/标签清单/源文件哈希，拒绝缺类、重复、冲突及非开发用途记录。
- `source_group_coverage()`：按视觉区域和原始比赛组计数；同一场比赛的多段录像、多个 session 或多张裁图不会增加独立比赛数。包素材不参与真实来源计数。

“用户确认同场”只能把这些片段归入一个组，不能证明该组与既有记录不同。缺少跨登记来源独立性确认时，该组仍是 provisional；不同视觉区域的来源不混合计算。

## 本地运行

下面的输入均为本地私有审计产物，使用调用者指定的路径，不在仓库中放原录像、包像素或机器路径：

```powershell
python -B -m workspace.vision.development_asset_intake `
  --package-map <private-dir>/tile_encoding_map.json `
  --recovery-manifest <private-dir>/real_source_recovery/crop_recovery_manifest.json `
  --source-records <private-dir>/real_source_recovery/source_records.json `
  --output <private-dir>/development_intake.json
```

输出使用独占创建，已有文件不会被覆盖。成功后可审阅 `counts`、`sources` 和 `source_coverage`。输出不是 `labels.jsonl`；每项素材 `approved=false`，所有 Runtime/Hint/Executor 与正式晋级标志为 false。工具使用标准库，不需要安装 OpenCV或接触小游戏。

## 输入和验证边界

包清单记录客户端编号、项目牌码、导出图、原图集、SpriteFrame元数据及各自SHA。完整性与编码对应检查不等于对图片内容的自动人工标注。

恢复裁图清单必须记录已完成的逐像素来源审计，以及裁图、当前模板、标签清单和源文件的SHA。**本工具重新检查文件身份，不重复解码录像或证明上游 `pixel_exact` 声明。** 源帧重建审计仍需单独保留；不能只构造一个声明成功的JSON来获取视觉可信度。

导入器读取经过哈希核验的标签JSONL，逐项绑定已审阅标签的ID、牌码、区域、来源SHA、session、帧号、模板名称及裁剪框；有标签图像SHA时同时核对。缺失、未审阅、重复ID或字段不一致均拒绝。相同比赛组存在矛盾的独立性声明时也拒绝，包含没有裁图的来源记录。

来源记录使用 `source_sha256`、`kind`、`original_match_group` 和来源审阅依据。只有明确的 `CONFIRMED_DISTINCT` 能计入审计中的已核验独立组；不通过session名称、录制时间或相似画面推断。此计数也只供开发诊断，不会授权Runtime接受身份。

## 已核验的本机切片

2026-10-13 已用真实私有数据运行导入器：34种标准牌＋8种花牌，79张恢复裁图，6个精确SHA源文件。用户确认五段录像同场，关联68张裁图；剩余11张来自一张已有回放记录的截图。截图SHA及父录像SHA形成到已有 `reviewed_recording_b389` 的别名证据，未创建新独立比赛。

公开证据摘要见 `references/vision/2026-10-13/development_asset_intake_v0_1.json`。原始像素、录像、本机路径、解密业务脚本和候选库均留在私有目录；仓库仅保留工具、测试与匿名元数据。

先前包模板对照在10月3日历史工作树的137张开发裁图上，原库93正确、合并候选99正确；6改善、0退化，但0.82阈值通过仍50、冻结真实支持门接受仍42，没有新增可接受输出。较新分支已有真实M2/N素材，不能用该旧工作树对照推断当前缺类状态。

## 接下来怎样使用

先用来源审计检查真实手牌/副露样本的缺口，保留已揭示开发素材与新锁定盲测的边界。候选素材只能进入隔离开发实验；任何正式Runtime晋级仍按 Issue [#7](https://github.com/shentianzhen1/Huian-Mahjong/issues/7) 的冻结门执行。

本切片不改变0.82阈值、Runtime加载路径、RuleSnapshot、CurrentAgent V0.10、Hint能力或Executor。完整手牌接受与真实副露检测路径仍需要对应的实战验证。
