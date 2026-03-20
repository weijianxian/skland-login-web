"""
数据存储层 - 使用 JSON 文件持久化用户数据和调度配置
"""

import json
import logging
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("Asia/Shanghai")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

_lock = threading.Lock()


@dataclass
class User:
    id: str  # 自动生成的唯一 ID
    token: str  # 鹰角通行证 token
    sendkey: str  # Server酱 push key
    scheduled_time: str  # 分配的签到时间  "HH:MM"
    notify_time_change: bool  # 是否通知签到时间变动
    created_at: str  # 创建时间 ISO 格式
    last_sign_at: str = ""  # 最后一次签到时间 ISO
    last_sign_result: str = ""  # 最后一次签到结果
    remark: str = ""  # 备注, 用户可编辑


@dataclass
class AppConfig:
    sign_start_hour: int = 6  # 签到窗口开始小时
    sign_start_minute: int = 0
    sign_end_hour: int = 12  # 签到窗口结束小时
    sign_end_minute: int = 0
    admin_password: str = "admin123"  # 管理面板密码


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_users() -> list[User]:
    _ensure_data_dir()
    if not os.path.exists(USERS_FILE):
        return []
    with _lock:
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [User(**u) for u in data]
        except Exception as e:
            logger.error(f"读取用户数据失败: {e}")
            return []


def save_users(users: list[User]):
    _ensure_data_dir()
    with _lock:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump([asdict(u) for u in users], f, ensure_ascii=False, indent=2)


def get_user_by_id(user_id: str) -> User | None:
    users = load_users()
    for u in users:
        if u.id == user_id:
            return u
    return None


def add_user(token: str, sendkey: str, scheduled_time: str, notify_time_change: bool = True, remark: str = "") -> User:
    users = load_users()
    # 检查 token 是否已存在
    for u in users:
        if u.token == token:
            raise ValueError("该 Token 已存在")
    import uuid

    user = User(
        id=uuid.uuid4().hex[:12],
        token=token,
        sendkey=sendkey,
        scheduled_time=scheduled_time,
        notify_time_change=notify_time_change,
        created_at=datetime.now(tz=TIMEZONE).isoformat(),
        remark=remark,
    )
    users.append(user)
    save_users(users)
    return user


def remove_user(user_id: str) -> User | None:
    users = load_users()
    removed = None
    new_users = []
    for u in users:
        if u.id == user_id:
            removed = u
        else:
            new_users.append(u)
    if removed:
        save_users(new_users)
    return removed


def remove_user_by_token(token: str) -> User | None:
    users = load_users()
    removed = None
    new_users = []
    for u in users:
        if u.token == token:
            removed = u
        else:
            new_users.append(u)
    if removed:
        save_users(new_users)
    return removed


def update_user(user_id: str, **kwargs) -> User | None:
    users = load_users()
    for u in users:
        if u.id == user_id:
            for k, v in kwargs.items():
                if hasattr(u, k):
                    setattr(u, k, v)
            save_users(users)
            return u
    return None


def load_config() -> AppConfig:
    _ensure_data_dir()
    if not os.path.exists(CONFIG_FILE):
        cfg = AppConfig()
        save_config(cfg)
        return cfg
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AppConfig(**data)
    except Exception as e:
        logger.error(f"读取配置失败: {e}")
        return AppConfig()


def save_config(config: AppConfig):
    _ensure_data_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, ensure_ascii=False, indent=2)
