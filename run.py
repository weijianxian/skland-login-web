#!/usr/bin/env python3
"""
森空岛自动签到 Web 服务启动脚本
"""

import os

import uvicorn

from src.app import create_app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app = create_app()
    print(
        f"""
    ╔═══════════════════════════════════════════════╗
    ║   森空岛自动签到 Web 服务已启动               ║
    ╠═══════════════════════════════════════════════╣
    ║   用户注册: http://localhost:{port:<4}           ║
    ║   管理面板: http://localhost:{port}/admin       ║
    ║   默认密码: admin123                          ║
    ╚═══════════════════════════════════════════════╝
    """
    )
    uvicorn.run(app, host="0.0.0.0", port=port, interface="wsgi")
