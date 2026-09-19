# NetDeploy Client Builder

GitHub Actions 自动构建 NetDeploy 装机机客户端 EXE

## 触发条件
- push 代码到 main 分支 → 自动构建
- 打 tag (v1.0.0) → 自动 Release

## 输出
- `dist/NetDeployClient.exe` (单文件,带 POWER BY 菁倍科技 品牌)
- 包含 ca.crt / client.crt / client.key (mTLS 证书)
- 自动创建 GitHub Release

## 下载
去 GitHub Releases 页面下载最新 EXE

## 文件
- `netdeploy_client.py` - 客户端 Python 源码
- `gen_version_info.py` - Windows EXE 元数据生成器 (菁倍科技中文品牌)
- `build_client.bat` - 本地构建脚本
- `version_info.txt` - EXE 版本信息
- `ca.crt` / `client.crt` / `client.key` - GB10 mTLS 证书

## 开发商
POWER BY 菁倍科技 · © 2026
