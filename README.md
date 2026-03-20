# 森空岛自动签到 Web 服务

基于 [skyland-auto-sign](https://gitee.com/FancyCabbage/skyland-auto-sign) 改造的 Web 版本，提供了用户友好的 Web 界面和管理后台。

## 主要特性

✅ **Web 界面注册** - 用户通过 Web 页面提交 Token 和 Server酱 推送密钥  
✅ **自动签到** - 每日自动执行签到，无需手动操作  
✅ **均衡时间分配** - 所有用户的签到时间在指定窗口内均匀分布  
✅ **Server酱通知** - 签到结果、时间变更、Token 失效自动推送  
✅ **管理面板** - 管理所有用户、配置签到时间窗口、手动触发签到  
✅ **自动清理** - 签到失败自动删除 Token 并通知用户  
✅ **时间变动通知** - 用户可选择是否在签到时间变更时接收通知

## 快速开始

### 1. 安装依赖

```bash
pip install -e .
```

或使用 uv (推荐):

```bash
uv pip install -e .
```

### 2. 运行应用

```bash
# 使用 uvicorn 启动
uv run run.py
```

默认运行在 `http://localhost:5000`

可通过环境变量配置端口:

```bash
PORT=8080 uv run run.py
```

### 3. 用户注册

1. 访问首页 `http://localhost:5000`
2. 按照页面说明获取鹰角网络通行证 Token
3. （可选）填写 Server酱 SendKey 接收通知
4. 提交后系统自动分配签到时间

### 4. 管理面板

访问 `http://localhost:5000/admin`

默认密码: `admin123` (首次登录后请在管理面板修改)

## 如何获取 Token

1. 登录 [森空岛官网](https://www.skland.com/)
2. 登录后访问 [此链接](https://web-api.skland.com/account/info/hg)
3. 复制页面返回的完整 JSON 内容，或仅复制 `data.content` 字段的值
4. 粘贴到注册页面的 Token 输入框

## Server酱配置

如需接收签到结果推送通知:

1. 注册 [Server酱³](https://sc3.ft07.com/)
2. 在手机上安装 Server酱³ App
3. 获取你的 SendKey (形如 `sctp12345tXXXX...`)
4. 在注册时填入 SendKey

## 管理面板功能

- **用户管理**: 查看所有注册用户、删除用户、手动触发签到
- **时间窗口配置**: 设置签到的起止时间范围
- **重新分配时间**: 手动触发所有用户签到时间的重新分配
- **任务监控**: 查看当前活跃的调度任务
- **密码修改**: 修改管理面板登录密码

## 数据存储

所有数据存储在 `data/` 目录下:

- `data/users.json` - 用户数据
- `data/config.json` - 系统配置

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `PORT` | Web 服务端口 | `5000` |
| `FLASK_SECRET_KEY` | Flask 会话密钥 | 随机生成 |
| `BUILD_COMMIT` | 构建提交号（页面底部显示） | `unknown` |

## 部署建议

### Docker 部署

本项目已提供 `Dockerfile`（基于 uv）和 `docker-compose.yml`。

方式一：直接使用 Docker

```bash
docker build --build-arg BUILD_COMMIT=$(git rev-parse --short=12 HEAD) -t skland-login-web .
docker run -d --name skland-login-web -p 5000:5000 -v ./data:/app/data -e FLASK_SECRET_KEY=your-random-secret -e BUILD_COMMIT=$(git rev-parse --short=12 HEAD) skland-login-web
```

方式二：使用 Docker Compose（推荐）

```bash
export BUILD_COMMIT=$(git rev-parse --short=12 HEAD)
docker compose up -d --build
```

查看日志:

```bash
docker compose logs -f
```

停止服务:

```bash
docker compose down
```

### systemd 服务

创建 `/etc/systemd/system/skland-web.service`:

```ini
[Unit]
Description=Skland Auto Sign Web
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/skland-login-web
Environment="PORT=5000"
ExecStart=/usr/bin/python3 /path/to/skland-login-web/src/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务:

```bash
sudo systemctl daemon-reload
sudo systemctl enable skland-web
sudo systemctl start skland-web
```

## 功能说明

### 签到时间均衡分配

系统会在管理员设置的时间窗口内（默认 6:00-22:00）为每个用户分配一个签到时间。算法会尽量让所有用户的签到时间均匀分布，避免同一时间大量请求。

当新用户加入或管理员修改时间窗口时，系统会自动重新分配所有用户的签到时间，并通知开启了时间变动通知的用户。

### 自动失效处理

如果用户签到失败（Token 失效、账号异常等），系统会:

1. 将该用户从数据库中删除
2. 移除对应的调度任务
3. 通过 Server酱 通知用户 Token 已失效（如果配置了 SendKey）

用户需要重新登录森空岛获取新 Token 并重新注册。

### 通知功能

系统支持以下通知场景（需配置 Server酱 SendKey）:

- **签到结果通知**: 每日签到完成后推送结果
- **时间变更通知**: 签到时间被重新分配时推送新时间
- **Token 失效通知**: 签到失败导致 Token 被删除时推送

## 技术栈

- **Web 框架**: Flask
- **任务调度**: APScheduler
- **数据存储**: JSON 文件
- **签到逻辑**: 基于原 skyland-auto-sign 项目
- **通知推送**: Server酱³

## 许可证

MIT License

## 致谢

基于 [skyland-auto-sign](https://gitee.com/FancyCabbage/skyland-auto-sign) 项目改造。
