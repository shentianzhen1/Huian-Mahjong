
from qzenv import QuanzhouEnvironment, Action, ActionType, CN
from qzenv.replay import save_events_jsonl

env = QuanzhouEnvironment()
state = env.reset(seed=42)

print("=== Quanzhou Mahjong Environment V0.1 Demo ===")
print("初始牌墙:", state.wall_remaining())

# 为了只演示环境机制，这里使用 scaffold rules。
state, ev = env.step(Action(player=state.current_player, type=ActionType.DRAW))
drawn = state.hands[0][-1]
print("玩家0摸牌:", CN.get(drawn, drawn))
print("牌墙剩余:", state.wall_remaining())

token = env.checkpoint()
state, ev = env.step(Action(player=0, type=ActionType.DISCARD, tile=drawn))
print("玩家0弃牌:", CN.get(drawn, drawn))
print("当前玩家:", state.current_player)

env.rollback(token)
print("回滚后当前玩家:", env.state.current_player)
print("回滚后玩家0手牌数:", len(env.state.hands[0]))

clone = env.clone()
print("clone state hash:", clone.state.state_hash())
print("原环境 state hash:", env.state.state_hash())

save_events_jsonl(env.events, "demo_events.jsonl")
print("事件牌谱已保存: demo_events.jsonl")
print("注意：V0.1 只验证环境层，不代表完整开心泉州二人规则。")
