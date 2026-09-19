# 远程控制助手 (NetDeploy 装机机器人)

## 简介

通过飞书聊天 → AI 理解 → 控制装机机的图形界面
让你**不用手动点鼠标**, AI 帮你装系统

## 完整链路

```
你 (飞书) 
  ↓ 发"点击新建虚拟机"
飞书云
  ↓ 公网 HTTPS POST
VM-0-5 (43.161.239.77:8094) ← webhook 中转
  ↓ Tailscale 内网转发
GB10 (100.95.97.21:8094) ← bot.py (AI 处理)
  ↓ 调 Qwen2.5-VL / Qwen2.5-Coder / Chroma
GB10 (100.95.97.21:8093) ← main.py (mTLS API)
  ↓
装机机客户端 (Windows EXE) ← pyautogui 执行
  ↓
Windows 鼠标键盘操作
```

## 已部署组件

| 组件 | 位置 | 状态 |
|---|---|---|
| 飞书 App "远程控制助手" | cli_aa2752cf6ef85be5 | ✅ 已发布 |
| VM-0-5 webhook 中转 v3 | 43.161.239.77:8094 | ✅ 跑着 |
| GB10 bot.py (飞书消息处理) | 100.95.97.21:8094 | ✅ 跑着 |
| GB10 main.py (mTLS API) | 100.95.97.21:8093 | ✅ 跑着 |
| GB10 main.py (admin UI) | 100.95.97.21:8091 | ✅ 跑着 |
| Chroma 向量数据库 | GB10 /root/netdeploy/data/chroma | ✅ 装好 |
| Qwen2.5-VL 视觉模型 | GB10 ollama | ✅ 装好 |
| Qwen2.5-Coder:32b LLM | GB10 ollama | ✅ 装好 |
| 装机机客户端 (待装) | Windows EXE | ⏳ 待你装 |

## 装机机客户端 - Windows 部署

### 下载

```
http://43.161.239.77/jbkj/public/netdeploy_client_full.zip
```

### 文件清单 (11KB)

| 文件 | 大小 | 用途 |
|---|---|---|
| `netdeploy_client.py` | 11.7 KB | 客户端 Python 源码 |
| `build_client.bat` | 1.9 KB | Windows 打包脚本 |
| `README_client.md` | 2.9 KB | 部署文档 |
| `ca.crt` | 2 KB | GB10 CA 证书 |
| `client.crt` | 1.4 KB | 客户端证书 |
| `client.key` | 1.7 KB | 客户端私钥 |

### 安装步骤

1. **下载 zip** → 解压
2. **装 Python 3.10+** (https://www.python.org/downloads/)
   - 安装时勾选 "Add Python to PATH"
3. **双击 `build_client.bat`**
   - 自动创建 venv (首次约 3 分钟装依赖)
   - PyInstaller 打包 (约 1-2 分钟)
4. **运行 `dist\NetDeployClient.exe`**
   - 启动后最小化到**系统托盘** (右下角)
   - 自动注册到 GB10 (状态: 待管理员审批)
5. **管理员批准** (下面有命令)

## 管理员批准 (你装机机连上后做一次)

GB10 上跑:

```bash
ssh gb10 "source /root/.train_venv/bin/activate && cd /root/netdeploy/server && python -c '
import requests
r = requests.get(\"https://127.0.0.1:8093/admin/api/clients\", verify=\"/root/netdeploy/certs/ca.crt\", cert=(\"/root/netdeploy/certs/client.crt\", \"/root/netdeploy/certs/client.key\"))
print(r.json())
'"
```

或者用浏览器访问 admin UI (只能 GB10 局域网):

```
http://100.95.97.21:8091/admin
```

## 装机机使用 (装机时)

```
装机机启动 NetDeployClient.exe
  ↓ 自动注册 + 心跳
GB10 收到 device_id
  ↓
你飞书发指令
  ↓
GB10 bot.py 处理 + AI 分析截图
  ↓
pyautogui 自动执行
```

## 飞书指令示例

| 你发 | AI 做 |
|---|---|
| `帮助` | 显示所有命令 |
| `状态` | 查装机机在线 |
| `截图` | 截装机机当前屏 + AI 分析 |
| `点击 XXX` | 找到 XXX 按钮位置 + 点击 |
| `输入 XXX` | 在焦点处输入文字 |
| `按键 XXX` | 按 F1/F5/Enter 键 |
| `确认` / `执行` | 执行上次 AI 建议 |
| `取消` / `停止` | 中止当前操作 |

## 完整装机流程 (示例: 在 vCenter 装 CentOS 7)

```
你: 截图
飞书: [返回当前屏幕截图 + AI 分析 "这是 vCenter 首页"]
你: 点击新建虚拟机
飞书: [AI 找"新建虚拟机"按钮坐标 + 截图确认]
你: 确认
飞书: [pyautogui 点击那个按钮] [返回新窗口截图 + 建议下一步]
你: 输入 centos7.iso
... (持续对话直到装机完成)
```

## 安全

- **mTLS 双向证书验证** — 只有装机机能连 GB10
- **client.key 私有** — 仅装机机本地存
- **GB10 只接受注册过的 device_id**
- **VM-0-5 webhook 仅做透明转发** — 不存任何用户数据

## 装机机客户端 — 系统要求

- Windows 10/11 x64
- Python 3.10+ (打包时)
- **Tailscale 客户端** — 连到 100.95.97.21 (必须)
- 显示器 (要截图)

## Tailscale 不在时怎么办?

如果装机机暂时没装 Tailscale:
- 不能连 GB10
- netdeploy 客户端连不上
- 需要先装 Tailscale → 加入 Tailnet → 重启 EXE

## 故障排查

### 装机机注册失败

1. 检查 Tailscale: `tailscale status` (应该有 100.x IP)
2. 检查网络: `ping 100.95.97.21`
3. 检查证书: ca.crt / client.crt / client.key 在 EXE 同目录
4. 看 log: `%APPDATA%\NetDeploy\client.log`

### 飞书找不到机器人

1. 飞书 → 我的应用 → 搜"远程控制助手"
2. 如果找不到, 飞书后台 → 应用发布 → 应用可用范围 → 加自己 → 发版

### 飞书指令没反应

1. GB10 main.py / bot.py 是否在跑: `ssh gb10 "ss -tlnp | grep 809"`
2. 装机机客户端是否在跑 (托盘图标)
3. 飞书后台 webhook URL: `http://43.161.239.77:8094/feishu/webhook`

## 装机机端权限 (装机系统时)

需要在装机机上**用管理员**运行 NetDeployClient.exe, 因为:
- pyautogui 模拟鼠标键盘需要前台窗口焦点
- 截图需要访问屏幕
- 如果装的系统需要管理员权限, pyautogui 也要管理员

## 最小演示流程 (5 分钟)

1. **下载 + 装 + 打包客户端** (~10 分钟)
2. **双击 NetDeployClient.exe** (注册成功显示托盘图标)
3. **飞书发 "状态"** → 看到装机机在线
4. **飞书发 "截图"** → 看到装机机当前屏幕 + AI 建议
5. **飞书发 "点击 XXX"** → AI 自动找位置 + 点击

## 文件位置

| 路径 | 内容 |
|---|---|
| `/tmp/netdeploy_client_full.zip` | 完整装机机包 |
| `/www/wwwroot/43.161.246.16/jbkj/public/netdeploy_client_full.zip` | jbkj 公网版本 |
| `/var/log/netdeploy_vm.log` | VM-0-5 webhook 中转 log |
| `/var/log/netdeploy_bot.log` | GB10 bot.py log |
| `/var/log/netdeploy_main.log` | GB10 main.py log |
| GB10 `/root/netdeploy/server/bot.py` | 飞书消息处理 |
| GB10 `/root/netdeploy/server/main.py` | API + admin |
| GB10 `/root/netdeploy/certs/` | mTLS 证书 |
| GB10 `/root/netdeploy/data/chroma/` | 装机步骤向量数据库 |

