#!/usr/bin/env python3
"""
生成 Windows EXE 版本信息文件 (UTF-8)
使用 PyInstaller 自带 API,避免文本 eval 问题
菁倍科技中文品牌 + POWER BY 菁倍科技
"""
import sys
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable,
    StringStruct, VarFileInfo, VarStruct
)

# UTF-8 编码版本信息
version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(1, 0, 0, 0),
        prodvers=(1, 0, 0, 0),
        mask=0x3f,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0)
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    '080404b0',  # 中文 (简体, 中国)
                    [
                        StringStruct('CompanyName', '菁倍科技'),
                        StringStruct('FileDescription', 'NetDeploy 装机机客户端 - POWER BY 菁倍科技'),
                        StringStruct('FileVersion', '1.0.0.0'),
                        StringStruct('InternalName', 'NetDeployClient'),
                        StringStruct('LegalCopyright', 'Copyright (C) 2026 菁倍科技'),
                        StringStruct('OriginalFilename', 'NetDeployClient.exe'),
                        StringStruct('ProductName', 'NetDeploy 装机助手 - POWER BY 菁倍科技'),
                        StringStruct('ProductVersion', '1.0.0.0')
                    ]
                )
            ]
        ),
        VarFileInfo([VarStruct('Translation', [2052, 1200])])
    ]
)

# 写到文件
output_path = sys.argv[1] if len(sys.argv) > 1 else "build/version_info.txt"
version_info.write(output_path)
print(f"[OK] Generated: {output_path}")
print(f"     CompanyName: 菁倍科技")
print(f"     ProductName: NetDeploy 装机助手 - POWER BY 菁倍科技")
print(f"     LegalCopyright: Copyright (C) 2026 菁倍科技")
