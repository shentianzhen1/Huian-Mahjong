# vision

窗口采集验证器已在 `capture_validator/` 实现。项目根目录运行
`START_CAPTURE_VALIDATOR.bat`，详见 `capture_validator/README.md`。
此工具只验证画面采集／保存，不连接 Rules、AI 或 Executor。

离线牌面识别原型位于 `tiles_v0_1/`，只处理自己的手牌区、新摸牌区和金牌展示区。使用流程见 `tiles_v0_1/README.md`，架构边界见 `VISION_V0_1_DESIGN.md`。
