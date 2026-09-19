#!/usr/bin/env python3
"""
NetDeploy 装机机客户端 (Windows)
- 启动后最小化到系统托盘
- 连接到 GB10 mTLS API (注册 + 心跳)
- 接收 GB10 指令 (截图 / 点击 / 输入 / 按键)
- 通过 pyautogui 执行操作
- 把截图回传给 GB10 (AI 视觉分析)

环境:
  pip install pyautogui pillow requests pystray PyQt5 mss
"""
import sys
import os
import json
import time
import base64
import threading
import queue
import logging
import ssl
from pathlib import Path
from datetime import datetime

# ====== 配置 ======
APP_NAME = "NetDeploy 装机助手"
APP_VENDOR = "菁倍科技"                    # 公司名
APP_BRAND = "POWER BY 菁倍科技"            # 品牌标识
APP_VERSION = "1.0.0"
APP_COPYRIGHT = f"© 2026 {APP_VENDOR} · All Rights Reserved"

GB10_API_BASE = "https://100.95.97.21:8093"  # GB10 mTLS API
CLIENT_ID = "PC-{hostname}-{user}".format(
    hostname=os.environ.get("COMPUTERNAME", "PC"),
    user=os.environ.get("USERNAME", "user"),
)
CA_CERT = "ca.crt"           # GB10 CA 证书
CLIENT_CERT = "client.crt"   # 客户端证书
CLIENT_KEY = "client.key"    # 客户端私钥
HEARTBEAT_INTERVAL = 10      # 心跳间隔 (秒)
SCREENSHOT_QUALITY = 70      # JPEG 质量

# ====== 日志 ======
LOG_DIR = Path(os.environ.get("APPDATA", ".")) / "NetDeploy"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "client.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("netdeploy-client")


# ====== 截图 ======
def screenshot_bytes():
    """截全屏, 返回 JPEG bytes"""
    try:
        import pyautogui
        img = pyautogui.screenshot()
    except ImportError:
        # 备用 mss
        import mss
        with mss.mss() as sct:
            img = sct.grab(sct.monitors[1])
            from PIL import Image
            img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
    from io import BytesIO
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=SCREENSHOT_QUALITY)
    return buf.getvalue()


# ====== 导入 pyautogui / requests ======
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.5
except ImportError:
    log.warning("⚠️ pyautogui 未装, 点击/输入指令将不可用")

import requests


# ====== GB10 API 客户端 (mTLS) ======
class GB10Client:
    def __init__(self):
        self.session = requests.Session()
        # 加载 mTLS 证书 (与 EXE 同目录)
        here = Path(__file__).parent
        ca = here / CA_CERT
        cert = (here / CLIENT_CERT, here / CLIENT_KEY)
        if ca.exists() and cert[0].exists() and cert[1].exists():
            self.session.verify = str(ca)
            self.session.cert = (str(cert[0]), str(cert[1]))
            log.info(f"✅ mTLS 证书加载: {cert[0].name}")
        else:
            log.warning(f"⚠️ mTLS 证书缺失, 跳过 (文件: ca.crt/client.crt/client.key)")

        self.token = None
        self.registered = False

    def _post(self, path, data):
        url = f"{GB10_API_BASE}{path}"
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            r = self.session.post(url, json=data, headers=headers, timeout=10)
            return r.json()
        except Exception as e:
            log.error(f"❌ API {path} 失败: {e}")
            return {"code": -1, "msg": str(e)}

    def register(self):
        """注册装机机到 GB10 (等待管理员审批)"""
        log.info(f"📝 注册装机机: {CLIENT_ID}")
        result = self._post("/api/auth/register", {
            "device_id": CLIENT_ID,
            "device_name": CLIENT_ID,
            "os": "Windows",
            "hostname": os.environ.get("COMPUTERNAME", ""),
        })
        log.info(f"   结果: {result}")
        if result.get("code") == 0:
            self.token = result.get("token")
            self.registered = True
        return result

    def heartbeat(self):
        """心跳 (告诉 GB10 我在线)"""
        return self._post("/api/auth/heartbeat", {
            "device_id": CLIENT_ID,
            "status": "online",
        })

    def upload_screenshot(self, jpeg_bytes, suggestion=""):
        """上传截图给 GB10 AI 分析"""
        return self._post("/api/vision/identify", {
            "device_id": CLIENT_ID,
            "image": base64.b64encode(jpeg_bytes).decode(),
            "context": suggestion,
        })

    def save_step(self, instruction, screenshot_b64, action_taken):
        """保存装机步骤到 Chroma"""
        return self._post("/api/steps/save", {
            "device_id": CLIENT_ID,
            "instruction": instruction,
            "screenshot": screenshot_b64,
            "action": action_taken,
        })


# ====== 指令执行 ======
def execute_command(cmd: dict):
    """执行 GB10 下发的指令"""
    action = cmd.get("action")
    log.info(f"⚡ 执行指令: {action} {cmd}")

    try:
        if action == "screenshot_now":
            # 触发截图
            jpg = screenshot_bytes()
            client = GB10Client()
            result = client.upload_screenshot(jpg, cmd.get("context", ""))
            log.info(f"   上传截图: {result}")
            return {"status": "screenshot_uploaded", "result": result}

        elif action == "click":
            # 点击 (通过 AI 视觉坐标)
            x, y = cmd.get("x"), cmd.get("y")
            target = cmd.get("target", "")
            if x is not None and y is not None:
                pyautogui.click(x, y)
                return {"status": "clicked", "x": x, "y": y}
            elif target:
                # 用 AI 找位置 (调用 GB10)
                client = GB10Client()
                jpg = screenshot_bytes()
                result = client.upload_screenshot(jpg, f"找 '{target}' 的位置")
                # 假设 GB10 返回坐标
                if "position" in result:
                    x, y = result["position"]["x"], result["position"]["y"]
                    pyautogui.click(x, y)
                    return {"status": "clicked_by_ai", "target": target, "x": x, "y": y}
                return {"status": "ai_not_found", "target": target}

        elif action == "double_click":
            x, y = cmd.get("x"), cmd.get("y")
            if x is not None and y is not None:
                pyautogui.doubleClick(x, y)
                return {"status": "double_clicked", "x": x, "y": y}

        elif action == "right_click":
            x, y = cmd.get("x"), cmd.get("y")
            if x is not None and y is not None:
                pyautogui.rightClick(x, y)
                return {"status": "right_clicked", "x": x, "y": y}

        elif action == "type":
            text = cmd.get("text", "")
            pyautogui.typewrite(text, interval=0.05)
            return {"status": "typed", "text": text[:50]}

        elif action == "press":
            key = cmd.get("key", "")
            pyautogui.press(key)
            return {"status": "pressed", "key": key}

        elif action == "hotkey":
            keys = cmd.get("keys", [])
            pyautogui.hotkey(*keys)
            return {"status": "hotkey", "keys": keys}

        elif action == "scroll":
            x, y = cmd.get("x"), cmd.get("y")
            clicks = cmd.get("clicks", 3)
            if x is not None and y is not None:
                pyautogui.scroll(clicks, x=x, y=y)
            else:
                pyautogui.scroll(clicks)
            return {"status": "scrolled", "clicks": clicks}

        elif action == "execute_suggestion":
            # 执行上次 AI 建议
            suggestion = cmd.get("context", {}).get("suggestion", {})
            if suggestion:
                return execute_command(suggestion)
            return {"status": "no_suggestion"}

        else:
            log.warning(f"⚠️ 未知指令: {action}")
            return {"status": "unknown_action", "action": action}

    except Exception as e:
        log.error(f"❌ 执行失败: {e}")
        return {"status": "error", "msg": str(e)}


# ====== 轮询 GB10 指令 ======
def poll_commands(stop_event):
    """轮询 GB10 拿指令 (短轮询, 简单可靠)"""
    client = GB10Client()
    while not stop_event.is_set():
        try:
            # 拉取待执行指令
            r = requests.get(
                f"{GB10_API_BASE}/api/client/pending",
                params={"device_id": CLIENT_ID},
                verify=str(Path(__file__).parent / CA_CERT) if (Path(__file__).parent / CA_CERT).exists() else False,
                cert=(str(Path(__file__).parent / CLIENT_CERT), str(Path(__file__).parent / CLIENT_KEY)) if (Path(__file__).parent / CLIENT_CERT).exists() else None,
                timeout=5,
            )
            data = r.json()
            for cmd in data.get("commands", []):
                log.info(f"📥 收到指令: {cmd}")
                result = execute_command(cmd)
                # 回报结果
                requests.post(
                    f"{GB10_API_BASE}/api/client/result",
                    json={"device_id": CLIENT_ID, "command_id": cmd.get("id"), "result": result},
                    verify=str(Path(__file__).parent / CA_CERT) if (Path(__file__).parent / CA_CERT).exists() else False,
                    timeout=5,
                )
        except Exception as e:
            log.warning(f"⚠️ 轮询失败: {e}")
        time.sleep(2)


# ====== 系统托盘 (PyQt5) ======
def make_brand_icon(app):
    """生成 POWER BY 菁倍科技 品牌图标 (PNG -> QPixmap)"""
    from PyQt5 import QtGui, QtCore
    # 用 QPainter 画一个带菁倍科技 logo 的图标
    pixmap = QtGui.QPixmap(64, 64)
    pixmap.fill(QtCore.Qt.transparent)

    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)

    # 圆形深蓝底
    painter.setBrush(QtGui.QColor("#1a3a5c"))
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawEllipse(2, 2, 60, 60)

    # 中心 JB 字母 (菁倍首字母)
    painter.setPen(QtGui.QColor("#ffffff"))
    font = QtGui.QFont("Microsoft YaHei", 22, QtGui.QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, "JB")

    painter.end()
    return QtGui.QIcon(pixmap)


def make_tray_app(stop_event):
    """最小化到系统托盘"""
    from PyQt5 import QtWidgets, QtGui, QtCore
    from PyQt5.QtCore import QTimer

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 应用元数据 (Windows 任务管理器 / 设置中显示)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_VENDOR)
    try:
        from PyQt5.QtCore import QCoreApplication
        QCoreApplication.setOrganizationName(APP_VENDOR)
        QCoreApplication.setApplicationName(APP_NAME)
    except Exception:
        pass

    # 托盘图标 (品牌图标)
    icon = make_brand_icon(app)
    tray = QtWidgets.QSystemTrayIcon(icon)
    tray.setToolTip(f"{APP_BRAND}\n{APP_NAME} · {CLIENT_ID}")

    menu = QtWidgets.QMenu()

    # 顶部品牌区 (不可点击)
    header = menu.addAction(f"⚙️ {APP_NAME}")
    header.setEnabled(False)
    header.setFont(QtGui.QFont("Microsoft YaHei", 9, QtGui.QFont.Bold))

    brand = menu.addAction(f"💎 {APP_BRAND}")
    brand.setEnabled(False)
    brand.setFont(QtGui.QFont("Microsoft YaHei", 8))

    menu.addSeparator()

    # 状态
    status_action = menu.addAction(f"✅ 已连接: {CLIENT_ID}")
    status_action.setEnabled(False)

    menu.addSeparator()

    # 操作
    screenshot_action = menu.addAction("📸 截图")
    screenshot_action.triggered.connect(lambda: execute_command({"action": "screenshot_now"}))

    help_action = menu.addAction("❓ 帮助")
    help_action.triggered.connect(lambda: show_help_dialog(app))

    about_action = menu.addAction("ℹ️ 关于")
    about_action.triggered.connect(lambda: show_about_dialog(app, tray))

    menu.addSeparator()

    # 版权 + 退出
    copyright_action = menu.addAction(f"📋 {APP_COPYRIGHT}")
    copyright_action.setEnabled(False)

    quit_action = menu.addAction("❌ 退出")
    quit_action.triggered.connect(lambda: (stop_event.set(), app.quit()))

    tray.setContextMenu(menu)
    tray.show()

    # 启动通知 (含品牌)
    tray.showMessage(
        APP_BRAND,
        f"{APP_NAME} v{APP_VERSION}\n"
        f"装机机: {CLIENT_ID}\n"
        f"{APP_COPYRIGHT}",
        QtWidgets.QSystemTrayIcon.Information,
        4000
    )

    # 双击托盘 → 显示关于对话框
    tray.activated.connect(lambda reason: (
        show_about_dialog(app, tray)
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick
        else None
    ))

    log.info(f"🖱️ 系统托盘已就绪 ({APP_BRAND})")

    return app


def show_about_dialog(app, tray=None):
    """显示关于对话框 - 含菁倍科技品牌"""
    from PyQt5 import QtWidgets, QtGui, QtCore

    box = QtWidgets.QMessageBox()
    box.setWindowTitle(f"关于 {APP_NAME}")
    box.setIcon(QtWidgets.QMessageBox.Information)

    text = (
        f"<h2 style='color:#1a3a5c;'>{APP_NAME}</h2>"
        f"<p style='font-size:14px;'><b>{APP_BRAND}</b></p>"
        f"<hr>"
        f"<table cellpadding='4'>"
        f"<tr><td><b>版本:</b></td><td>v{APP_VERSION}</td></tr>"
        f"<tr><td><b>开发商:</b></td><td>{APP_VENDOR}</td></tr>"
        f"<tr><td><b>装机机:</b></td><td>{CLIENT_ID}</td></tr>"
        f"<tr><td><b>GB10:</b></td><td>{GB10_API_BASE}</td></tr>"
        f"<tr><td><b>心跳:</b></td><td>{HEARTBEAT_INTERVAL}s</td></tr>"
        f"</table>"
        f"<hr>"
        f"<p style='color:gray;font-size:11px;'>{APP_COPYRIGHT}</p>"
    )
    box.setText(text)
    box.setStandardButtons(QtWidgets.QMessageBox.Ok)
    box.exec_()


def show_help_dialog(app):
    """显示帮助"""
    from PyQt5 import QtWidgets

    box = QtWidgets.QMessageBox()
    box.setWindowTitle(f"{APP_NAME} - 帮助")
    box.setIcon(QtWidgets.QMessageBox.Information)

    text = (
        f"<h3>{APP_NAME} - 使用说明</h3>"
        f"<p><b>{APP_BRAND}</b></p>"
        f"<hr>"
        f"<p><b>使用方法:</b></p>"
        f"<ol>"
        f"<li>飞书搜索 '远程控制助手' 机器人</li>"
        f"<li>双击托盘图标查看连接状态</li>"
        f"<li>在飞书发语音/文字指令</li>"
        f"<li>AI 自动执行装机操作</li>"
        f"</ol>"
        f"<p><b>飞书常用命令:</b></p>"
        f"<ul>"
        f"<li><code>截图</code> - 截取装机机当前屏</li>"
        f"<li><code>状态</code> - 检查装机机状态</li>"
        f"<li><code>点击XXX</code> - 点击屏幕元素</li>"
        f"<li><code>输入XXX</code> - 输入文本</li>"
        f"<li><code>确认</code> - 执行 AI 建议</li>"
        f"</ul>"
        f"<hr>"
        f"<p style='color:gray;font-size:11px;'>{APP_COPYRIGHT}</p>"
    )
    box.setText(text)
    box.setStandardButtons(QtWidgets.QMessageBox.Ok)
    box.exec_()


def show_splash_screen():
    """启动画面 - POWER BY 菁倍科技 品牌"""
    try:
        from PyQt5 import QtWidgets, QtGui, QtCore

        # 用 QPixmap 画启动画面
        splash_pix = QtGui.QPixmap(480, 280)
        splash_pix.fill(QtGui.QColor("#f0f4f8"))

        painter = QtGui.QPainter(splash_pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # 顶部品牌色
        painter.setBrush(QtGui.QColor("#1a3a5c"))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRect(0, 0, 480, 80)

        # 应用名
        painter.setPen(QtGui.QColor("#ffffff"))
        title_font = QtGui.QFont("Microsoft YaHei", 22, QtGui.QFont.Bold)
        painter.setFont(title_font)
        painter.drawText(QtCore.QRect(0, 15, 480, 50), QtCore.Qt.AlignCenter, APP_NAME)

        # POWER BY 菁倍科技
        painter.setPen(QtGui.QColor("#1a3a5c"))
        brand_font = QtGui.QFont("Microsoft YaHei", 13, QtGui.QFont.Bold)
        painter.setFont(brand_font)
        painter.drawText(QtCore.QRect(0, 100, 480, 30), QtCore.Qt.AlignCenter, APP_BRAND)

        # 版本号
        ver_font = QtGui.QFont("Microsoft YaHei", 10)
        painter.setFont(ver_font)
        painter.setPen(QtGui.QColor("#666"))
        painter.drawText(QtCore.QRect(0, 140, 480, 20), QtCore.Qt.AlignCenter, f"版本 v{APP_VERSION}")

        # 装机机 ID
        id_font = QtGui.QFont("Consolas", 10)
        painter.setFont(id_font)
        painter.setPen(QtGui.QColor("#333"))
        painter.drawText(QtCore.QRect(0, 165, 480, 20), QtCore.Qt.AlignCenter, f"装机机: {CLIENT_ID}")

        # GB10
        gb_font = QtGui.QFont("Consolas", 9)
        painter.setFont(gb_font)
        painter.setPen(QtGui.QColor("#888"))
        painter.drawText(QtCore.QRect(0, 185, 480, 20), QtCore.Qt.AlignCenter, f"GB10: {GB10_API_BASE}")

        # 版权
        cp_font = QtGui.QFont("Microsoft YaHei", 8)
        painter.setFont(cp_font)
        painter.setPen(QtGui.QColor("#aaa"))
        painter.drawText(QtCore.QRect(0, 240, 480, 20), QtCore.Qt.AlignCenter, APP_COPYRIGHT)

        painter.end()

        splash = QtWidgets.QSplashScreen(splash_pix)
        splash.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint)
        splash.show()
        QtWidgets.QApplication.processEvents()
        return splash
    except Exception as e:
        log.warning(f"⚠️ 启动画面创建失败: {e}")
        return None


def main():
    log.info(f"🚀 NetDeploy 装机机客户端启动: {CLIENT_ID}")
    log.info(f"   {APP_BRAND} v{APP_VERSION}")

    # 启动画面 (必须在 QApplication 创建后)
    splash = None
    try:
        from PyQt5 import QtWidgets
        _tmp_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        splash = show_splash_screen()
        if splash:
            import time as _t
            _t.sleep(1.2)  # 让用户看到启动画面
    except Exception as e:
        log.warning(f"⚠️ 启动画面跳过: {e}")

    # 1. 注册到 GB10
    client = GB10Client()
    register_result = client.register()
    if not client.registered:
        log.error(f"❌ 注册失败: {register_result}")
        log.info("继续运行, 可手动重试注册")
    else:
        if splash:
            splash.showMessage(f"已连接到 GB10\n{CLIENT_ID}",
                              QtCore.Qt.AlignBottom | QtCore.Qt.AlignCenter,
                              QtCore.Qt.white)

    # 2. 启动心跳
    def heartbeat_loop():
        while True:
            try:
                client.heartbeat()
            except Exception as e:
                log.warning(f"心跳失败: {e}")
            time.sleep(HEARTBEAT_INTERVAL)
    threading.Thread(target=heartbeat_loop, daemon=True).start()

    # 3. 启动指令轮询
    stop_event = threading.Event()
    threading.Thread(target=poll_commands, args=(stop_event,), daemon=True).start()

    # 4. 系统托盘
    try:
        app = make_tray_app(stop_event)
        log.info("进入系统托盘模式")
        sys.exit(app.exec_())
    except Exception as e:
        log.error(f"托盘启动失败: {e}, 改用前台模式")
        # 没有 PyQt5 时, 直接前台跑
        try:
            while not stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            stop_event.set()


if __name__ == "__main__":
    main()
