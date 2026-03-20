"""
Server酱推送通知模块
"""

import logging
import re
from datetime import date

import requests

logger = logging.getLogger(__name__)


def send_serverchan(sendkey: str, title: str, desp: str, tags: str = "") -> bool:
    """
    通过 Server酱 发送通知
    :param sendkey: Server酱 SendKey (形如 sctp12345tXXXX...)
    :param title: 通知标题
    :param desp: 通知内容 (支持 Markdown)
    :param tags: 标签列表，多个标签使用竖线分隔 (如 "标签1|标签2")
    :return: 是否发送成功
    """
    if not sendkey:
        return False

    uid = None
    m = re.match(r"^sctp(\d+)t", sendkey)
    if m:
        uid = m.group(1)
    else:
        logger.error("无法从 sendkey 中提取 uid，请检查 sendkey 格式")
        return False

    api = f"https://{uid}.push.ft07.com/send/{sendkey}.send"
    payload = {"title": title, "desp": desp}
    if tags:
        payload["tags"] = tags

    try:
        r = requests.post(api, json=payload, timeout=10)
        if r.status_code == 200:
            logger.info(f"Server酱推送成功: {title}")
            return True
        else:
            logger.error(f"Server酱推送失败, HTTP {r.status_code}: {r.text}")
            return False
    except Exception as e:
        logger.error(f"Server酱推送异常: {e}")
        return False


def notify_sign_result(sendkey: str, logs: list[str]):
    """签到结果通知"""
    if not sendkey:
        return
    title = f"森空岛签到结果 - {date.today().strftime('%Y-%m-%d')}"
    desp = "  \n".join(line.rstrip() for line in logs) if logs else "无签到记录"
    send_serverchan(sendkey, title, desp, tags="森空岛|签到结果")


def notify_time_change(sendkey: str, new_time: str):
    """签到时间变更通知"""
    if not sendkey:
        return
    title = "森空岛签到时间变更通知"
    desp = f"您的每日签到时间已调整为: **{new_time}**\n\n系统将在该时间自动为您签到。"
    send_serverchan(sendkey, title, desp, tags="森空岛|时间变更")


def notify_token_removed(sendkey: str, reason: str):
    """Token 失效删除通知"""
    if not sendkey:
        return
    title = "森空岛签到 Token 已失效"
    desp = f"您的 Token 已失效并被移除。\n\n**原因**: {reason}\n\n请重新登录并提交新的 Token。"
    send_serverchan(sendkey, title, desp, tags="森空岛|Token失效")
