import multiprocessing as mp
import os
import queue
import time


def dpi_awareness():
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass


def windows():
    import win32gui
    import win32process
    own = os.getpid()
    found = []
    def visit(hwnd, _):
        title = win32gui.GetWindowText(hwnd)
        if title and win32gui.IsWindowVisible(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid != own:
                found.append((hwnd, pid, title))
    win32gui.EnumWindows(visit, None)
    return sorted(found, key=lambda item: item[2])


def geometry(hwnd, pid):
    import win32gui
    import win32process
    if not win32gui.IsWindow(hwnd) or win32process.GetWindowThreadProcessId(hwnd)[1] != pid:
        raise RuntimeError("目标窗口已关闭或被替换")
    if win32gui.IsIconic(hwnd):
        raise RuntimeError("目标窗口已最小化，请恢复后重新开始")
    rect = win32gui.GetWindowRect(hwnd)
    if rect[2] <= rect[0] or rect[3] <= rect[1]:
        raise RuntimeError("窗口尺寸无效")
    return rect


def print_window(hwnd, rect):
    import ctypes
    import win32gui
    import win32ui
    from PIL import Image
    width, height = rect[2] - rect[0], rect[3] - rect[1]
    dc = win32gui.GetWindowDC(hwnd)
    source = target = bitmap = None
    old = None
    try:
        source = win32ui.CreateDCFromHandle(dc)
        target = source.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source, width, height)
        old = target.SelectObject(bitmap)
        fn = ctypes.windll.user32.PrintWindow
        fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
        fn.restype = ctypes.c_int
        if not fn(hwnd, target.GetSafeHdc(), 2):
            raise RuntimeError("PrintWindow 失败；请手动选择其他后端")
        return Image.frombytes("RGB", (width, height), bitmap.GetBitmapBits(True), "raw", "BGRX")
    finally:
        if target and old:
            target.SelectObject(old)
        if bitmap:
            win32gui.DeleteObject(bitmap.GetHandle())
        if target:
            target.DeleteDC()
        if source:
            source.DeleteDC()
        if dc:
            win32gui.ReleaseDC(hwnd, dc)


def offer(out, message):
    try:
        out.put_nowait(message)
    except queue.Full:
        pass  # Bounded queue: skip a frame instead of accumulating latency.


def wgc_frame_to_image(frame):
    """Copy the mapped WGC buffer before the native callback returns."""
    from PIL import Image
    bgr = frame.convert_to_bgr().frame_buffer
    return Image.fromarray(bgr[:, :, ::-1].copy())


def worker(hwnd, pid, backend, out, stop):
    dpi_awareness()
    sequence = 0
    last = 0.0
    def emit(image, rect):
        nonlocal sequence, last
        now = time.monotonic()
        if now - last < .095:
            return
        last = now
        sequence += 1
        offer(out, ("frame", sequence, now, time.time(), image.size, image.tobytes(), rect))
    try:
        geometry(hwnd, pid)
        if backend == "WGC":
            from windows_capture import WindowsCapture
            capture = WindowsCapture(cursor_capture=False, draw_border=True,
                                     monitor_index=None, window_hwnd=hwnd)
            @capture.event
            def on_frame_arrived(frame, control):
                try:
                    if stop.is_set():
                        control.stop()
                        return
                    if time.monotonic() - last < .095:
                        return
                    rect = geometry(hwnd, pid)
                    emit(wgc_frame_to_image(frame), rect)
                except Exception as exc:
                    offer(out, ("error", str(exc)))
                    stop.set()
                    control.stop()
            @capture.event
            def on_closed():
                offer(out, ("error", "WGC 捕获会话已关闭"))
                stop.set()
            capture.start()  # UI can terminate this isolated process if native calls hang.
        else:
            from PIL import ImageGrab
            while not stop.is_set():
                rect = geometry(hwnd, pid)
                image = print_window(hwnd, rect) if backend == "PrintWindow" else ImageGrab.grab(
                    bbox=rect, all_screens=True
                ).convert("RGB")
                emit(image, rect)
                stop.wait(.1)
    except Exception as exc:
        offer(out, ("error", f"{type(exc).__name__}: {exc}"))


class CaptureSession:
    def __init__(self, hwnd, pid, backend):
        if backend not in ("WGC", "PrintWindow", "屏幕区域"):
            raise ValueError("未知采集后端")
        context = mp.get_context("spawn")
        self.out = context.Queue(maxsize=2)
        self.stop_event = context.Event()
        self.process = context.Process(target=worker, args=(hwnd, pid, backend, self.out, self.stop_event), daemon=True)
        self.process.start()

    def read(self):
        latest = None
        for _ in range(3):
            try:
                item = self.out.get_nowait()
            except queue.Empty:
                break
            if item[0] == "error":
                return item
            latest = item
        return latest

    def close(self):
        self.stop_event.set()
        self.process.join(.25)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(1)
        self.out.cancel_join_thread()
        self.out.close()
