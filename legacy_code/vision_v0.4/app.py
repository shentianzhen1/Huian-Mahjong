
import json, time, traceback
from pathlib import Path
from collections import deque
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
import numpy as np
from PIL import Image, ImageTk
import win32gui, win32ui

APP_DIR = Path(__file__).resolve().parent
CFG_PATH = APP_DIR / "config.json"
BAD_DIR = APP_DIR / "data" / "bad_frames"
SNAP_DIR = APP_DIR / "data" / "snapshots"

def load_cfg():
    return json.loads(CFG_PATH.read_text(encoding="utf-8"))

def save_cfg(cfg):
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

def enum_windows():
    items=[]
    def cb(hwnd,_):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title=win32gui.GetWindowText(hwnd).strip()
        if not title:
            return
        try:
            l,t,r,b=win32gui.GetWindowRect(hwnd)
            if r-l >= 300 and b-t >= 200:
                items.append((hwnd,title))
        except Exception:
            pass
    win32gui.EnumWindows(cb,None)
    return items

def capture_window(hwnd):
    l,t,r,b=win32gui.GetWindowRect(hwnd)
    w,h=r-l,b-t
    if w <= 0 or h <= 0:
        raise RuntimeError("Invalid mirror window size.")

    hwndDC=win32gui.GetWindowDC(hwnd)
    mfcDC=win32ui.CreateDCFromHandle(hwndDC)
    saveDC=mfcDC.CreateCompatibleDC()
    bmp=win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfcDC,w,h)
    saveDC.SelectObject(bmp)

    ok=0
    try:
        ok=win32gui.PrintWindow(hwnd,saveDC.GetSafeHdc(),2)
    except Exception:
        ok=0

    info=bmp.GetInfo()
    data=bmp.GetBitmapBits(True)
    img=np.frombuffer(data,dtype=np.uint8).reshape((info["bmHeight"],info["bmWidth"],4))
    img=cv2.cvtColor(img,cv2.COLOR_BGRA2BGR)

    win32gui.DeleteObject(bmp.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd,hwndDC)

    if ok != 1 or img.mean() < 2:
        import mss
        with mss.mss() as sct:
            raw=np.array(sct.grab({"left":l,"top":t,"width":w,"height":h}))
            img=cv2.cvtColor(raw,cv2.COLOR_BGRA2BGR)
    return img

def rect_to_norm(rect,shape):
    x,y,w,h=rect
    H,W=shape[:2]
    return [x/W,y/H,(x+w)/W,(y+h)/H]

def crop_norm(frame,roi):
    if not roi:
        return None
    H,W=frame.shape[:2]
    x1,y1,x2,y2=roi
    a,b,c,d=int(x1*W),int(y1*H),int(x2*W),int(y2*H)
    return frame[max(0,b):min(H,d),max(0,a):min(W,c)].copy()

def segment(roi):
    if roi is None or roi.size == 0:
        return [],None

    hsv=cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,(0,0,110),(180,165,255))
    kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(3,3))
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,kernel,iterations=2)
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,kernel,iterations=1)

    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    H,W=roi.shape[:2]
    boxes=[]
    for c in contours:
        x,y,w,h=cv2.boundingRect(c)
        area=w*h
        if h < H*0.28:
            continue
        if area < H*W*0.002 or area > H*W*0.18:
            continue
        ar=w/max(1,h)
        if 0.20 <= ar <= 1.25:
            boxes.append((x,y,w,h))

    boxes=sorted(boxes,key=lambda z:z[0])

    dbg=roi.copy()
    for i,(x,y,w,h) in enumerate(boxes,1):
        cv2.rectangle(dbg,(x,y),(x+w,y+h),(0,255,0),2)
        cv2.putText(dbg,str(i),(x,max(15,y-4)),
                    cv2.FONT_HERSHEY_SIMPLEX,.5,(0,255,0),1,cv2.LINE_AA)
    return boxes,dbg

class Chooser(tk.Toplevel):
    def __init__(self,master):
        super().__init__(master)
        self.title("Select mirror window")
        self.geometry("680x430")
        self.result=None
        self.items=enum_windows()
        self.listbox=tk.Listbox(self)
        self.listbox.pack(fill="both",expand=True,padx=10,pady=10)
        for _,title in self.items:
            self.listbox.insert("end",title)
        ttk.Button(self,text="Use selected window",command=self.use).pack(pady=8)
        self.listbox.bind("<Double-1>",lambda e:self.use())
        self.grab_set()

    def use(self):
        sel=self.listbox.curselection()
        if not sel:
            return
        self.result=self.items[sel[0]]
        self.destroy()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Quanzhou Mahjong Assistant V0.4 - Two-player / iPhone")
        self.geometry("1180x760")
        self.minsize(980,650)

        self.cfg=load_cfg()
        self.hwnd=None
        self.running=False
        self.last=None
        self.last_sig=None
        self.stable=0
        self.counts=deque(maxlen=5)
        self.photo=None
        self.last_bad=0
        self.build()

    def build(self):
        top=ttk.Frame(self,padding=8)
        top.pack(fill="x")
        ttk.Button(top,text="1. Select mirror window",command=self.choose).pack(side="left")
        ttk.Button(top,text="2. Calibrate hand ROI",command=lambda:self.calibrate("hand_roi")).pack(side="left",padx=5)
        ttk.Button(top,text="3. Calibrate draw ROI",command=lambda:self.calibrate("draw_roi")).pack(side="left")
        ttk.Button(top,text="Start monitoring",command=self.start).pack(side="left",padx=(15,5))
        ttk.Button(top,text="Stop",command=self.stop).pack(side="left")
        ttk.Button(top,text="Save snapshot",command=self.snapshot).pack(side="left",padx=12)

        self.status=tk.StringVar(value="Ready")
        ttk.Label(self,textvariable=self.status,padding=8).pack(fill="x")

        pan=ttk.Panedwindow(self,orient="horizontal")
        pan.pack(fill="both",expand=True,padx=8,pady=8)

        left=ttk.Frame(pan)
        right=ttk.Frame(pan,width=300)
        pan.add(left,weight=4)
        pan.add(right,weight=1)

        self.video=tk.Label(left,bg="black",fg="white",text="No video")
        self.video.pack(fill="both",expand=True)

        self.lw=ttk.Label(right,text="Mirror: not selected",wraplength=280)
        self.lw.pack(anchor="w",pady=4)
        self.ls=ttk.Label(right,text="Stable frames: 0")
        self.ls.pack(anchor="w",pady=4)
        self.lh=ttk.Label(right,text="Hand candidates: -")
        self.lh.pack(anchor="w",pady=4)
        self.ld=ttk.Label(right,text="Draw candidates: -")
        self.ld.pack(anchor="w",pady=4)
        self.lq=ttk.Label(right,text="Recognition quality: waiting")
        self.lq.pack(anchor="w",pady=4)

        ttk.Separator(right).pack(fill="x",pady=12)
        ttk.Label(right,text="Mode: TWO-PLAYER first").pack(anchor="w")
        ttk.Label(right,text="Input: iPhone mirror window\nCapture card: not used").pack(anchor="w",pady=6)
        ttk.Label(right,text="V0.4 goal:\nStable capture + tile segmentation.\nNo strong AI yet.",
                  wraplength=280,justify="left").pack(anchor="w",pady=12)

    def choose(self):
        c=Chooser(self)
        self.wait_window(c)
        if c.result:
            self.hwnd,title=c.result
            self.lw.config(text="Mirror: "+title)
            self.last=capture_window(self.hwnd)
            self.render(self.last)
            self.status.set("Mirror selected. Calibrate hand ROI.")

    def calibrate(self,key):
        if not self.hwnd:
            messagebox.showinfo("Info","Select mirror window first.")
            return
        frame=capture_window(self.hwnd)
        title="Drag around your HAND" if key=="hand_roi" else "Drag around DRAW tile area"
        rect=cv2.selectROI(title,frame,False,False)
        cv2.destroyAllWindows()
        if rect[2] > 5 and rect[3] > 5:
            self.cfg[key]=rect_to_norm(rect,frame.shape)
            save_cfg(self.cfg)
            self.status.set(("Hand ROI" if key=="hand_roi" else "Draw ROI")+" saved.")

    def start(self):
        if not self.hwnd:
            messagebox.showinfo("Info","Select mirror window first.")
            return
        if not self.cfg.get("hand_roi"):
            messagebox.showinfo("Info","Calibrate hand ROI first.")
            return
        self.running=True
        self.status.set("Monitoring...")
        self.after(10,self.loop)

    def stop(self):
        self.running=False
        self.status.set("Stopped.")

    def loop(self):
        if not self.running:
            return
        try:
            frame=capture_window(self.hwnd)
            self.last=frame

            gray=cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),(160,90))
            if self.last_sig is None:
                delta=999.0
            else:
                delta=float(np.mean(cv2.absdiff(gray,self.last_sig)))
            self.last_sig=gray
            self.stable=self.stable+1 if delta<2.8 else 0

            hand=crop_norm(frame,self.cfg.get("hand_roi"))
            draw=crop_norm(frame,self.cfg.get("draw_roi"))
            hb,hdbg=segment(hand)
            db,_=segment(draw)

            self.counts.append(len(hb))
            consistent=len(self.counts)>=3 and max(self.counts)-min(self.counts)<=1
            plausible=8 <= len(hb) <= 20
            good=self.stable>=self.cfg.get("stable_required_frames",4) and consistent and plausible

            self.ls.config(text=f"Stable frames: {self.stable}  Δ{delta:.2f}")
            self.lh.config(text=f"Hand candidates: {len(hb)}")
            self.ld.config(text=f"Draw candidates: {len(db)}")
            self.lq.config(text="Recognition quality: GOOD" if good else "Recognition quality: CHECK")

            vis=frame.copy()
            H,W=vis.shape[:2]
            for key,color,name in [
                ("hand_roi",(0,255,0),"HAND"),
                ("draw_roi",(0,255,255),"DRAW")
            ]:
                roi=self.cfg.get(key)
                if roi:
                    x1,y1,x2,y2=roi
                    p1=(int(x1*W),int(y1*H))
                    p2=(int(x2*W),int(y2*H))
                    cv2.rectangle(vis,p1,p2,color,2)
                    cv2.putText(vis,name,(p1[0],max(20,p1[1]-5)),
                                cv2.FONT_HERSHEY_SIMPLEX,.55,color,2)

            if hdbg is not None and hdbg.size:
                ih=min(210,max(100,H//3))
                scale=ih/hdbg.shape[0]
                iw=min(W//2,int(hdbg.shape[1]*scale))
                ih=int(hdbg.shape[0]*(iw/hdbg.shape[1]))
                inset=cv2.resize(hdbg,(iw,ih))
                vis[H-ih:H,W-iw:W]=inset

            self.render(vis)

            if not good and self.stable>=self.cfg.get("stable_required_frames",4):
                now=time.time()
                if now-self.last_bad>=self.cfg.get("bad_frame_cooldown_sec",8):
                    self.last_bad=now
                    cv2.imwrite(str(BAD_DIR/f"bad_{time.strftime('%Y%m%d_%H%M%S')}.jpg"),frame)

        except Exception as e:
            self.running=False
            messagebox.showerror("Error",str(e)+"\n\n"+traceback.format_exc()[-800:])
            return

        self.after(self.cfg.get("frame_interval_ms",120),self.loop)

    def render(self,frame):
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        img=Image.fromarray(rgb)
        maxw=max(500,self.video.winfo_width()-10)
        maxh=max(350,self.video.winfo_height()-10)
        img.thumbnail((maxw,maxh),Image.Resampling.LANCZOS)
        self.photo=ImageTk.PhotoImage(img)
        self.video.config(image=self.photo,text="")

    def snapshot(self):
        if self.last is None:
            return
        path=SNAP_DIR/f"snapshot_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(str(path),self.last)
        self.status.set("Saved: "+path.name)

if __name__=="__main__":
    App().mainloop()
