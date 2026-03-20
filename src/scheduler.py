"""
调度器模块 - 管理每日签到任务的均衡时间分布
"""

import logging
import random
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import storage
from .notifier import notify_sign_result, notify_time_change, notify_token_removed
from .skyland import do_sign

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def _execute_sign(user_id: str):
    """执行单个用户的签到"""
    user = storage.get_user_by_id(user_id)
    if user is None:
        logger.warning(f"用户 {user_id} 不存在，跳过签到")
        return

    logger.info(f"开始为用户 {user_id} (备注: {user.remark}) 执行签到")
    success, logs = do_sign(user.token)

    now = datetime.now().isoformat()
    if success:
        storage.update_user(user_id, last_sign_at=now, last_sign_result="成功: " + "; ".join(logs))
        logger.info(f"用户 {user_id} 签到成功")
        notify_sign_result(user.sendkey, logs)
    else:
        logger.warning(f"用户 {user_id} 签到失败: {logs}")
        # 签到失败 -> 删除 token 并通知用户
        reason = "; ".join(logs) if logs else "未知错误"
        storage.update_user(user_id, last_sign_at=now, last_sign_result="失败(已移除): " + reason)
        # 通知用户 token 已失效
        notify_token_removed(user.sendkey, reason)
        # 移除用户
        storage.remove_user(user_id)
        # 移除调度任务
        job_id = f"sign_{user_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        logger.info(f"用户 {user_id} 已因签到失败被移除")


def allocate_time(config: storage.AppConfig, existing_users: list[storage.User]) -> str:
    """
    在指定时间窗口内为新用户分配一个均衡分散的签到时间。
    尽量让所有用户的签到时间均匀分布在窗口内。
    """
    start_minutes = config.sign_start_hour * 60 + config.sign_start_minute
    end_minutes = config.sign_end_hour * 60 + config.sign_end_minute
    total_window = end_minutes - start_minutes
    if total_window <= 0:
        total_window = 24 * 60  # fallback

    # 收集已有时间
    used_minutes = set()
    for u in existing_users:
        try:
            parts = u.scheduled_time.split(":")
            used_minutes.add(int(parts[0]) * 60 + int(parts[1]))
        except (ValueError, IndexError):
            pass

    n = len(used_minutes) + 1  # 包含即将新增的用户

    if n == 1:
        # 唯一用户，随机选一个在窗口中间附近的时间
        offset = random.randint(start_minutes, end_minutes)
    else:
        # 均匀分布: 将窗口分成 n 段，找到空隙最大的位置
        slot_size = total_window / n
        # 尝试找到一个没有太多冲突的位置
        best_minute = start_minutes
        best_min_distance = -1
        for _ in range(50):  # 随机采样50次
            candidate = random.randint(start_minutes, end_minutes)
            # 计算与所有已有时间的最小距离
            if not used_minutes:
                best_minute = candidate
                break
            min_dist = min(abs(candidate - m) for m in used_minutes)
            if min_dist > best_min_distance:
                best_min_distance = min_dist
                best_minute = candidate
        offset = best_minute

    hour = offset // 60
    minute = offset % 60
    return f"{hour:02d}:{minute:02d}"


def reallocate_all_times():
    """
    重新分配所有用户的签到时间（均衡分布）。
    当管理员修改时间窗口设置后调用。
    """
    config = storage.load_config()
    users = storage.load_users()
    if not users:
        return

    start_minutes = config.sign_start_hour * 60 + config.sign_start_minute
    end_minutes = config.sign_end_hour * 60 + config.sign_end_minute
    total_window = end_minutes - start_minutes
    if total_window <= 0:
        total_window = 24 * 60

    n = len(users)
    # 均匀分配 + 小随机偏移
    interval = total_window / n if n > 0 else total_window

    for i, user in enumerate(users):
        base = start_minutes + int(i * interval)
        jitter = random.randint(0, max(1, int(interval * 0.3)))  # 30% 偏移
        offset = min(base + jitter, end_minutes)
        new_time = f"{offset // 60:02d}:{offset % 60:02d}"
        old_time = user.scheduled_time
        user.scheduled_time = new_time

        # 如果时间变了而且用户开了通知
        if old_time != new_time and user.notify_time_change:
            notify_time_change(user.sendkey, new_time)

    storage.save_users(users)
    # 重新加载调度
    reload_all_jobs()


def schedule_user(user: storage.User):
    """为单个用户添加调度任务"""
    job_id = f"sign_{user.id}"
    try:
        parts = user.scheduled_time.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
    except (ValueError, IndexError):
        hour, minute = 8, 0

    # 如果已经存在则先移除
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
        _execute_sign,
        CronTrigger(hour=hour, minute=minute),
        args=[user.id],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info(f"已为用户 {user.id} 添加每日 {user.scheduled_time} 的签到任务")


def reload_all_jobs():
    """重新加载所有用户的调度任务"""
    # 移除所有 sign_ 开头的任务
    for job in scheduler.get_jobs():
        if job.id.startswith("sign_"):
            scheduler.remove_job(job.id)

    users = storage.load_users()
    for user in users:
        schedule_user(user)
    logger.info(f"已重新加载 {len(users)} 个签到任务")


def init_scheduler():
    """初始化调度器并加载所有已有任务"""
    if not scheduler.running:
        scheduler.start()
    reload_all_jobs()
    logger.info("调度器已启动")
