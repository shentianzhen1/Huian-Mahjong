
import tkinter as tk
from tkinter import ttk, messagebox
from qzcore.tiles import BASE_TILES, CN, validate_tile_multiset
from qzcore.win_checker import can_win, winning_decompositions
from qzcore.ting import ting_tiles
from qzcore.legal_actions import can_peng, can_ming_gang, can_an_gang, chi_options
from qzcore.scoring import two_player_net_score
from qzcore.rules import load_rules

rules = load_rules()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Quanzhou Mahjong Core V0.1 - Manual Tester")
        self.geometry("1180x820")
        self.hand=[]
        self.gold=tk.StringVar(value="")
        self.open_melds=tk.IntVar(value=0)
        self.win_type=tk.StringVar(value="zimo")
        self.discard=tk.StringVar(value="")
        self.build()
        self.refresh_hand()

    def build(self):
        ttk.Label(self, text="开心泉州二人麻将 · Core V0.1 手动规则测试器",
                  font=("Microsoft YaHei",16,"bold")).pack(pady=(12,6))

        top=ttk.Frame(self,padding=8); top.pack(fill="x")
        ttk.Label(top,text="金牌:").pack(side="left")
        ttk.Combobox(top,textvariable=self.gold,values=[""]+list(BASE_TILES),
                     width=8,state="readonly").pack(side="left",padx=5)
        ttk.Label(top,text="已副露组数:").pack(side="left",padx=(20,4))
        ttk.Spinbox(top,from_=0,to=5,textvariable=self.open_melds,width=5).pack(side="left")
        ttk.Label(top,text="胡牌方式:").pack(side="left",padx=(20,4))
        ttk.Combobox(top,textvariable=self.win_type,
                     values=["zimo","pinghu","qianggang"],width=10,state="readonly").pack(side="left")
        ttk.Button(top,text="清空手牌",command=self.clear).pack(side="right")
        ttk.Button(top,text="撤销最后一张",command=self.undo).pack(side="right",padx=6)

        handf=ttk.LabelFrame(self,text="当前手牌",padding=8); handf.pack(fill="x",padx=10,pady=5)
        self.hand_label=ttk.Label(handf,text="",font=("Microsoft YaHei",13))
        self.hand_label.pack(anchor="w")
        self.count_label=ttk.Label(handf,text="0 张")
        self.count_label.pack(anchor="w",pady=(4,0))

        grid=ttk.LabelFrame(self,text="点击加入手牌",padding=8); grid.pack(fill="x",padx=10,pady=5)
        row=0; col=0
        for t in BASE_TILES:
            ttk.Button(grid,text=CN[t],width=7,command=lambda x=t:self.add_tile(x)).grid(row=row,column=col,padx=2,pady=2)
            col += 1
            if col == 9:
                row += 1; col=0

        actions=ttk.Frame(self,padding=8); actions.pack(fill="x")
        ttk.Button(actions,text="分析：胡 / 听",command=self.analyze).pack(side="left")
        ttk.Label(actions,text="对手刚打:").pack(side="left",padx=(18,4))
        ttk.Combobox(actions,textvariable=self.discard,values=[""]+list(BASE_TILES),
                     width=8,state="readonly").pack(side="left")
        ttk.Button(actions,text="检查 吃/碰/杠",command=self.check_actions).pack(side="left",padx=6)

        self.result=tk.Text(self,height=14,font=("Consolas",11))
        self.result.pack(fill="both",expand=True,padx=10,pady=5)

        score=ttk.LabelFrame(self,text="二人结算验证",padding=8); score.pack(fill="x",padx=10,pady=(5,10))
        self.wb=tk.IntVar(value=5); self.wf=tk.IntVar(value=24)
        self.lb=tk.IntVar(value=10); self.lf=tk.IntVar(value=2)
        self.mult=tk.IntVar(value=2)
        for label,var in [("胜方底",self.wb),("胜方番",self.wf),("负方底",self.lb),("负方番",self.lf),("倍率",self.mult)]:
            ttk.Label(score,text=label).pack(side="left")
            ttk.Entry(score,textvariable=var,width=5).pack(side="left",padx=(2,10))
        ttk.Button(score,text="计算净分",command=self.calc_score).pack(side="left")

    def add_tile(self,t):
        self.hand.append(t); self.refresh_hand()

    def undo(self):
        if self.hand: self.hand.pop()
        self.refresh_hand()

    def clear(self):
        self.hand.clear(); self.refresh_hand()

    def refresh_hand(self):
        self.hand_label.config(text=" ".join(CN.get(t,t) for t in self.hand) or "（空）")
        self.count_label.config(text=f"{len(self.hand)} 张")

    def log(self,s):
        self.result.insert("end",s+"\n")
        self.result.see("end")

    def analyze(self):
        self.result.delete("1.0","end")
        ok,msg=validate_tile_multiset(self.hand,include_flowers=False)
        self.log(f"合法性: {msg}")
        if not ok: return
        g=self.gold.get() or None
        wm=self.win_type.get()
        open_melds=self.open_melds.get()

        target_win=(5-open_melds)*3+2
        target_ting=target_win-1
        self.log(f"当前张数: {len(self.hand)}；该副露数下，完整胡牌手牌应为 {target_win} 张，听牌手牌应为 {target_ting} 张。")
        if len(self.hand)==target_win:
            cw=can_win(self.hand,gold_tile=g,open_melds=open_melds,win_type=wm)
            self.log(f"可胡: {'是' if cw else '否'}")
            if cw:
                sols=winning_decompositions(self.hand,gold_tile=g,open_melds=open_melds,max_solutions=3)
                for i,sol in enumerate(sols,1):
                    pair=" + ".join(CN.get(x,x) if x!="GOLD" else "金" for x in sol["pair"])
                    groups=["-".join(CN.get(x,x) if x!="GOLD" else "金" for x in grp) for grp in sol["groups"]]
                    self.log(f"  结构{i}: 将[{pair}] | " + " / ".join(groups))
        elif len(self.hand)==target_ting:
            ts=ting_tiles(self.hand,gold_tile=g,open_melds=open_melds,win_type=wm)
            if not ts:
                self.log("听牌: 否")
            else:
                self.log("听牌: 是")
                self.log("可胡: " + "、".join(f"{CN[x['tile']]}(理论剩{x['remaining']}张)" for x in ts))
        else:
            self.log("张数不对应当前副露数下的胡牌/听牌测试入口。")

    def check_actions(self):
        d=self.discard.get()
        if not d:
            messagebox.showinfo("提示","先选择“对手刚打”的牌。")
            return
        g=self.gold.get() or None
        allow_chi=rules.get("allow_chi") is True
        self.log(f"\n针对对手打出 {CN[d]}:")
        self.log(f"碰: {'可' if can_peng(self.hand,d,g) else '不可'}")
        self.log(f"明杠: {'可' if can_ming_gang(self.hand,d,g) else '不可'}")
        opts=chi_options(self.hand,d,allow_chi=allow_chi,gold_tile=g)
        if rules.get("allow_chi") is None:
            self.log("吃: 二人房规则尚未确认（当前不自动允许）")
        else:
            self.log("吃: " + (" / ".join("-".join(CN[x] for x in o) for o in opts) if opts else "不可"))
        gangs=[CN[t] for t in BASE_TILES if can_an_gang(self.hand,t,g)]
        self.log("暗杠: " + ("、".join(gangs) if gangs else "无"))

    def calc_score(self):
        try:
            net=two_player_net_score(self.wb.get(),self.wf.get(),self.lb.get(),self.lf.get(),multiplier=self.mult.get())
            self.log(f"\n结算: [({self.wb.get()}+{self.wf.get()})-({self.lb.get()}+{self.lf.get()})]×{self.mult.get()} = {net}")
            self.log(f"胜方 {net:+d}，负方 {-net:+d}")
        except Exception as e:
            self.log("结算错误: "+str(e))

if __name__=="__main__":
    App().mainloop()
