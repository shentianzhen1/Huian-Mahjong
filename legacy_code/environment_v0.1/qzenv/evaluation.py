
from dataclasses import dataclass

@dataclass
class MatchStats:
    games: int = 0
    wins: list[int] | None = None
    net_scores: list[int] | None = None

    def __post_init__(self):
        if self.wins is None:
            self.wins = [0, 0]
        if self.net_scores is None:
            self.net_scores = [0, 0]

    def add_result(self, rewards):
        if len(rewards) != 2:
            raise ValueError("V0.1 评测器按二人麻将设计")
        self.games += 1
        self.net_scores[0] += rewards[0]
        self.net_scores[1] += rewards[1]
        if rewards[0] > rewards[1]:
            self.wins[0] += 1
        elif rewards[1] > rewards[0]:
            self.wins[1] += 1

    def assert_zero_sum(self):
        if sum(self.net_scores) != 0:
            raise AssertionError(f"累计净分不守恒: {self.net_scores}")

def paired_wall_seeds(n, base_seed=1000):
    """
    固定牌墙复式评测骨架：
    每个 seed 运行两次，第二次交换座位/庄闲。
    真正的对局执行器将在 Simulator 层接入。
    """
    for i in range(n):
        seed = base_seed + i
        yield {"seed": seed, "swap_seats": False}
        yield {"seed": seed, "swap_seats": True}
