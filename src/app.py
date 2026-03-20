"""
Flask Web 应用 - 森空岛自动签到 Web 服务
"""

import logging
import os
import subprocess


from flask import Flask, render_template, request, redirect, url_for, flash, session

from . import storage
from . import scheduler as sched_module
from .skyland import parse_token

logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"),
    static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "skland-auto-sign-secret-key-change-me")


def _resolve_build_commit() -> str:
    for key in ("BUILD_COMMIT", "GIT_COMMIT", "COMMIT_SHA"):
        value = os.environ.get(key, "").strip()
        if value:
            return value[:12]

    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return commit or "unknown"
    except Exception:
        return "unknown"


BUILD_COMMIT = _resolve_build_commit()


@app.context_processor
def inject_build_meta():
    return {"build_commit": BUILD_COMMIT}


# ------------------------------------------------------------------
# 用户页面
# ------------------------------------------------------------------


@app.route("/")
def index():
    """用户注册/提交 Token 页面"""
    return render_template("index.html")


@app.route("/register", methods=["POST"])
def register():
    """用户提交 Token"""
    raw_token = request.form.get("token", "").strip()
    sendkey = request.form.get("sendkey", "").strip()
    remark = request.form.get("remark", "").strip()
    notify = request.form.get("notify_time_change") == "on"

    if not raw_token:
        flash("Token 不能为空", "error")
        return redirect(url_for("index"))

    # 解析 token (支持粘贴完整 JSON)
    token = parse_token(raw_token)
    if not token:
        flash("Token 格式无效", "error")
        return redirect(url_for("index"))

    config = storage.load_config()
    users = storage.load_users()

    # 分配签到时间
    scheduled_time = sched_module.allocate_time(config, users)

    try:
        user = storage.add_user(
            token=token,
            sendkey=sendkey,
            scheduled_time=scheduled_time,
            notify_time_change=notify,
            remark=remark,
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("index"))

    # 添加调度任务
    sched_module.schedule_user(user)

    flash(f"注册成功! 您的每日签到时间为 {scheduled_time}，用户ID: {user.id}", "success")
    return redirect(url_for("index"))


@app.route("/delete-by-token", methods=["POST"])
def delete_by_token():
    """用户通过 token 删除自己的账号"""
    raw_token = request.form.get("token", "").strip()

    if not raw_token:
        flash("Token 不能为空", "error")
        return redirect(url_for("index"))

    token = parse_token(raw_token)
    if not token:
        flash("Token 格式无效", "error")
        return redirect(url_for("index"))

    removed = storage.remove_user_by_token(token)
    if not removed:
        flash("未找到对应 Token 的账号", "error")
        return redirect(url_for("index"))

    job_id = f"sign_{removed.id}"
    if sched_module.scheduler.get_job(job_id):
        sched_module.scheduler.remove_job(job_id)

    flash("账号已删除，自动签到任务已移除", "success")
    return redirect(url_for("index"))


# ------------------------------------------------------------------
# 管理面板
# ------------------------------------------------------------------


@app.route("/admin")
def admin_login_page():
    """管理面板登录页"""
    if session.get("is_admin"):
        return redirect(url_for("admin_panel"))
    return render_template("admin_login.html")


@app.route("/admin/login", methods=["POST"])
def admin_login():
    """管理面板登录"""
    password = request.form.get("password", "")
    config = storage.load_config()
    if password == config.admin_password:
        session["is_admin"] = True
        return redirect(url_for("admin_panel"))
    flash("密码错误", "error")
    return redirect(url_for("admin_login_page"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login_page"))


@app.route("/admin/panel")
def admin_panel():
    """管理面板主页"""
    if not session.get("is_admin"):
        return redirect(url_for("admin_login_page"))
    users = storage.load_users()
    config = storage.load_config()
    jobs = []
    for job in sched_module.scheduler.get_jobs():
        if job.id.startswith("sign_"):
            jobs.append({"id": job.id, "next_run": str(job.next_run_time) if job.next_run_time else "N/A"})
    return render_template("admin.html", users=users, config=config, jobs=jobs)


@app.route("/admin/config", methods=["POST"])
def admin_update_config():
    """更新签到时间窗口配置"""
    if not session.get("is_admin"):
        return redirect(url_for("admin_login_page"))

    try:
        start_hour = int(request.form.get("sign_start_hour", 6))
        start_minute = int(request.form.get("sign_start_minute", 0))
        end_hour = int(request.form.get("sign_end_hour", 22))
        end_minute = int(request.form.get("sign_end_minute", 0))
        admin_password = request.form.get("admin_password", "").strip()
    except ValueError:
        flash("请输入有效的数字", "error")
        return redirect(url_for("admin_panel"))

    config = storage.load_config()
    old_start = config.sign_start_hour * 60 + config.sign_start_minute
    old_end = config.sign_end_hour * 60 + config.sign_end_minute

    config.sign_start_hour = start_hour
    config.sign_start_minute = start_minute
    config.sign_end_hour = end_hour
    config.sign_end_minute = end_minute
    if admin_password:
        config.admin_password = admin_password
    storage.save_config(config)

    new_start = start_hour * 60 + start_minute
    new_end = end_hour * 60 + end_minute

    # 如果时间窗口变了，重新分配所有用户时间
    if old_start != new_start or old_end != new_end:
        sched_module.reallocate_all_times(notify_users=False)
        flash("配置已更新，所有用户签到时间已重新分配（不发送通知）", "success")
    else:
        flash("配置已更新", "success")

    return redirect(url_for("admin_panel"))


@app.route("/admin/user/<user_id>/delete", methods=["POST"])
def admin_delete_user(user_id):
    """删除用户"""
    if not session.get("is_admin"):
        return redirect(url_for("admin_login_page"))

    removed = storage.remove_user(user_id)
    if removed:
        job_id = f"sign_{user_id}"
        if sched_module.scheduler.get_job(job_id):
            sched_module.scheduler.remove_job(job_id)
        flash(f"用户 {user_id} 已删除", "success")
    else:
        flash("用户不存在", "error")

    return redirect(url_for("admin_panel"))


@app.route("/admin/user/<user_id>/sign", methods=["POST"])
def admin_trigger_sign(user_id):
    """手动触发签到"""
    if not session.get("is_admin"):
        return redirect(url_for("admin_login_page"))

    import threading

    threading.Thread(target=sched_module._execute_sign, args=(user_id,), daemon=True).start()
    flash(f"已触发用户 {user_id} 的签到任务（后台执行中）", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/reallocate", methods=["POST"])
def admin_reallocate():
    """重新分配所有用户的签到时间"""
    if not session.get("is_admin"):
        return redirect(url_for("admin_login_page"))

    sched_module.reallocate_all_times(notify_users=True)
    flash("所有用户签到时间已重新分配，已通知开启时间变动通知的用户", "success")
    return redirect(url_for("admin_panel"))


# ------------------------------------------------------------------
# 启动入口
# ------------------------------------------------------------------


def create_app():
    """创建并初始化应用"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # 初始化调度器
    sched_module.init_scheduler()
    return app


if __name__ == "__main__":
    application = create_app()
    port = int(os.environ.get("PORT", 5000))
    application.run(host="0.0.0.0", port=port, debug=False)
