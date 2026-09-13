泉州二人麻将环境层 Quanzhou_Mahjong_Env_V0.1

定位：
这是 Rules 和 Simulator 之间的“Environment 环境层”骨架。
本版不继续猜尚未确认的规则，也不训练AI、不做视觉识别、不自动点击。

已经实现：
- GameState 统一状态
- Action / ActionType
- EventLog 事件牌谱
- reset()
- legal_actions()
- step(action)
- clone()
- checkpoint()
- rollback()
- is_terminal()
- get_reward()
- 固定牌墙复式评测 seeds 骨架
- 二人零和净分断言
- 自动测试

为什么要有这一层：
Rules 负责“能不能这么做”
Environment 负责“这么做之后状态怎么变化”
Simulator 负责“不断调用 Environment 把整局跑完”
AI 负责“从合法动作里选哪个最好”

运行：
1. 解压 ZIP
2. 双击 RUN_TESTS.bat，应该看到全部测试 OK
3. 双击 RUN_DEMO.bat，可看一次 draw -> discard -> rollback -> clone 的演示

说明：
当前 ScaffoldRules 只是为了测试环境层结构，绝对不代表完整开心泉州二人麻将规则。
等专业规则讲解补齐后，会替换为正式 QuanzhouRulesAdapter，不需要推倒 Environment。
