import sys
import os
import shutil
import json
import time
import collections
import asyncio
import threading
import http.server
import socketserver
import keyboard
import websockets

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView

HTTP_PORT = 8080
WS_PORT = 8765

# ================= 1. 文件持久化与资源路径 =================
def get_base_path():
    """获取打包后的资源目录 (sys._MEIPASS) 或开发环境当前目录"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def get_exe_dir():
    """获取生成的 .exe 所在同级目录，用于持久化存储"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
EXE_DIR = get_exe_dir()

CONFIG_FILE = os.path.join(EXE_DIR, "config.json")
STATS_FILE = os.path.join(EXE_DIR, "stats.json")

# 启动时检测：如果 exe 同级目录没有 json，则从包内解压释放出来
for filename in ["config.json", "stats.json"]:
    dest = os.path.join(EXE_DIR, filename)
    src = os.path.join(BASE_DIR, filename)
    if not os.path.exists(dest) and os.path.exists(src):
        try:
            shutil.copy2(src, dest)
        except Exception as e:
            print(f"提取 {filename} 失败: {e}")

# ================= 2. 原 server.py 核心逻辑 =================
connected_clients = set()

config = {
    "scale": 1.0,
    "autoHide": {"enabled": False, "compact": False, "compactDir": "center", "sessionCount": False},
    "groups": {
        "group_1": {
            "name": "区域1", "enabled": True, "x": 5, "y": 75, "direction": "right",
            "keys": [{"key": "W", "color": "#39C5BB"}, {"key": "A", "color": "#39C5BB"}, {"key": "S", "color": "#39C5BB"}, {"key": "D", "color": "#39C5BB"}]
        },
        "group_2": {
            "name": "区域2", "enabled": True, "x": 50, "y": 85, "direction": "up",
            "keys": [{"key": "Q", "color": "#FF69B4"}, {"key": "E", "color": "#FF69B4"}, {"key": "U", "color": "#FF69B4"}, {"key": "O", "color": "#FF69B4"}]
        },
        "group_3": {
            "name": "区域3", "enabled": True, "x": 95, "y": 75, "direction": "left",
            "keys": [{"key": "I", "color": "#39C5BB"}, {"key": "J", "color": "#39C5BB"}, {"key": "K", "color": "#39C5BB"}, {"key": "L", "color": "#39C5BB"}]
        }
    }
}

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        try: config.update(json.load(f))
        except: pass

stats = {"total": 0, "keys": {}}
if os.path.exists(STATS_FILE):
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        try: stats.update(json.load(f))
        except: pass

key_times = {}
key_last = {}
pressed_keys = set()
stats_dirty = False

def configured_key_set():
    s = set()
    for g in config.get("groups", {}).values():
        for k in g.get("keys", []):
            s.add(str(k.get("key", "")).upper())
    return s

def record_key(key):
    global stats_dirty
    known = stats["keys"]
    if key not in known and key not in configured_key_set():
        return
    now = time.time()
    entry = known.setdefault(key, {"count": 0, "peak": 0, "active": 0.0})
    entry["count"] += 1
    stats["total"] = stats.get("total", 0) + 1
    last = key_last.get(key)
    if last is not None:
        gap = now - last
        if gap > 0:
            entry["active"] += min(gap, 2.0)
    key_last[key] = now
    dq = key_times.setdefault(key, collections.deque())
    dq.append(now)
    while dq and now - dq[0] > 1.0:
        dq.popleft()
    if len(dq) > entry.get("peak", 0):
        entry["peak"] = len(dq)
    stats_dirty = True

def stats_payload():
    keys = {}
    for k, e in stats["keys"].items():
        active = e.get("active", 0.0)
        avg = round(e["count"] / active, 2) if active > 0 else float(e["count"])
        keys[k] = {"count": e["count"], "peak": e.get("peak", 0), "avg": avg}
    return {"total": stats.get("total", 0), "keys": keys}

def save_stats():
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

async def stats_flusher():
    global stats_dirty
    while True:
        await asyncio.sleep(5)
        if stats_dirty:
            stats_dirty = False
            save_stats()
            msg = json.dumps({"type": "stats", "data": stats_payload()})
            for client in list(connected_clients):
                try: await client.send(msg)
                except Exception: pass

async def ws_handler(websocket):
    global stats_dirty
    connected_clients.add(websocket)
    await websocket.send(json.dumps({"type": "config", "data": config}))
    await websocket.send(json.dumps({"type": "stats", "data": stats_payload()}))
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "update_config":
                config.update(data["data"])
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=4)
                for client in connected_clients:
                    await client.send(json.dumps({"type": "config", "data": config}))
            
            elif msg_type == "reset_stats":
                stats["total"] = 0
                stats["keys"] = {}
                key_times.clear()
                key_last.clear()
                stats_dirty = True
                save_stats()
                for client in connected_clients:
                    await client.send(json.dumps({"type": "reset_stats"}))
                    await client.send(json.dumps({"type": "stats", "data": stats_payload()}))
            
            elif msg_type == "refresh":
                for client in connected_clients:
                    await client.send(json.dumps({"type": "refresh"}))
    except Exception:
        pass
    finally:
        connected_clients.remove(websocket)

def on_key_event(event):
    key = event.name.upper()
    if event.event_type == keyboard.KEY_DOWN:
        if key in pressed_keys:
            return
        pressed_keys.add(key)
        state = "down"
        record_key(key)
    else:
        pressed_keys.discard(key)
        state = "up"
    message = json.dumps({"type": "key", "key": key, "state": state})
    for client in list(connected_clients):
        try: client.loop.call_soon_threadsafe(asyncio.create_task, client.send(message))
        except: pass

# ================= 3. 后台服务线程 =================
def start_websocket_server():
    """在独立线程中启动 WebSocket 与热键监听"""
    async def backend_main():
        keyboard.hook(on_key_event)
        asyncio.create_task(stats_flusher())
        async with websockets.serve(ws_handler, "127.0.0.1", WS_PORT):
            await asyncio.Future()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(backend_main())

def start_http_server():
    """提供本地 HTTP 服务供 OBS 或内嵌网页加载 HTML"""
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=BASE_DIR, **kwargs)
        def log_message(self, format, *args):
            pass # 屏蔽 HTTP 日志
    httpd = socketserver.TCPServer(("127.0.0.1", HTTP_PORT), Handler)
    httpd.serve_forever()

# ================= 4. UI 与系统托盘 =================
class OverlayWindow(QWebEngineView):
    def __init__(self):
        super().__init__()
        # 核心：无边框 + 置顶 + 鼠标穿透 + 背景透明
        self.setWindowFlags(
            Qt.Window |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.WindowTransparentForInput |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.page().setBackgroundColor(Qt.transparent)
        self.load(QUrl(f"http://127.0.0.1:{HTTP_PORT}/index.html"))

    def fill_screen(self):
        """让透明窗口铺满整个屏幕，交由 HTML 内部自动计算 16:9 比例居中"""
        # 获取当前屏幕完整的分辨率范围（包含任务栏等区域）
        rect = self.screen().geometry()
        self.setGeometry(rect)

def create_tray_icon():
    """绘制一个纯色圆形的默认托盘图标"""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#39C5BB")) 
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(4, 4, 56, 56)
    painter.end()
    return QIcon(pixmap)

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    overlay = OverlayWindow()
    # 【关键修复】：必须先 show 分配系统句柄，再强制设置全屏尺寸
    overlay.show() 
    overlay.fill_screen()

    tray = QSystemTrayIcon(create_tray_icon(), app)
    menu = QMenu()

    # 菜单项：开关覆盖层
    toggle_action = QAction("隐藏屏幕覆盖层", app)
    def toggle_overlay():
        if overlay.isVisible():
            overlay.hide()
            toggle_action.setText("显示屏幕覆盖层")
        else:
            # 重新显示时，再次确保铺满屏幕（防止期间用户修改了分辨率）
            overlay.show()
            overlay.fill_screen()
            toggle_action.setText("隐藏屏幕覆盖层")
    toggle_action.triggered.connect(toggle_overlay)
    menu.addAction(toggle_action)
    menu.addSeparator()

    # 菜单项：复制链接
    copy_obs_action = QAction("复制 OBS 捕获链接", app)
    copy_obs_action.triggered.connect(lambda: app.clipboard().setText(f"http://127.0.0.1:{HTTP_PORT}/index.html"))
    menu.addAction(copy_obs_action)

    copy_console_action = QAction("复制后台控制面板地址", app)
    copy_console_action.triggered.connect(lambda: app.clipboard().setText(f"http://127.0.0.1:{HTTP_PORT}/config.html"))
    menu.addAction(copy_console_action)
    menu.addSeparator()

    # 菜单项：退出
    quit_action = QAction("退出程序", app)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.show()

    # 启动后台常驻服务
    threading.Thread(target=start_http_server, daemon=True).start()
    threading.Thread(target=start_websocket_server, daemon=True).start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()