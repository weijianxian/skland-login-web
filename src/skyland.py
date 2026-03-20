"""
森空岛签到核心模块
仅保留签到相关函数，去除所有交互式登录和环境变量逻辑
"""

import hashlib
import hmac
import json
import logging
import time
from urllib import parse

import requests

from .security_sm import get_d_id

logger = logging.getLogger(__name__)

APP_CODE = "4ca99fa6b56cc2ba"


def parse_token(raw: str) -> str:
    """
    解析用户输入的 token。
    支持直接粘贴 content 值，也支持粘贴完整的 JSON 响应 (含 data.content)。
    """
    raw = raw.strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict) and "data" in obj and "content" in obj["data"]:
            return obj["data"]["content"]
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return raw


HEADER = {
    "cred": "",
    "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-A5560 Build/V417IR; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/101.0.4951.61 Safari/537.36; SKLand/1.52.1",
    "Accept-Encoding": "gzip",
    "Connection": "close",
    "X-Requested-With": "com.hypergryph.skland",
}

HEADER_LOGIN = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-A5560 Build/V417IR; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/101.0.4951.61 Safari/537.36; SKLand/1.52.1",
    "Accept-Encoding": "gzip",
    "Connection": "close",
    "dId": get_d_id(),
    "X-Requested-With": "com.hypergryph.skland",
}

HEADER_FOR_SIGN = {
    "platform": "3",
    "timestamp": "",
    "dId": HEADER_LOGIN["dId"],
    "vName": "1.0.0",
}

# 签到 URL
SIGN_URL_MAPPING = {
    "arknights": "https://zonai.skland.com/api/v1/game/attendance",
    "endfield": "https://zonai.skland.com/web/v1/game/endfield/attendance",
}

BINDING_URL = "https://zonai.skland.com/api/v1/game/player/binding"
GRANT_CODE_URL = "https://as.hypergryph.com/user/oauth2/v2/grant"
CRED_CODE_URL = "https://zonai.skland.com/web/v1/user/auth/generate_cred_by_code"


def _generate_signature(token: str, path: str, body_or_query: str):
    t = str(int(time.time()) - 2)
    token_bytes = token.encode("utf-8")
    header_ca = json.loads(json.dumps(HEADER_FOR_SIGN))
    header_ca["timestamp"] = t
    header_ca_str = json.dumps(header_ca, separators=(",", ":"))
    s = path + body_or_query + t + header_ca_str
    hex_s = hmac.new(token_bytes, s.encode("utf-8"), hashlib.sha256).hexdigest()
    md5 = hashlib.md5(hex_s.encode("utf-8")).hexdigest()
    return md5, header_ca


def _get_sign_header(url: str, method: str, body, headers: dict, token: str):
    p = parse.urlparse(url)
    if method.lower() == "get":
        sign, header_ca = _generate_signature(token, p.path, p.query)
    else:
        sign, header_ca = _generate_signature(token, p.path, json.dumps(body) if body is not None else "")
    headers["sign"] = sign
    for k in header_ca:
        headers[k] = header_ca[k]
    return headers


def get_cred_by_token(hg_token: str) -> dict:
    """使用鹰角通行证 token 获取 cred 和 sign token"""
    grant_code = _get_grant_code(hg_token)
    return _get_cred(grant_code)


def _get_grant_code(token: str) -> str:
    response = requests.post(
        GRANT_CODE_URL,
        json={"appCode": APP_CODE, "token": token, "type": 0},
        headers=HEADER_LOGIN,
    )
    resp = response.json()
    if response.status_code != 200:
        raise Exception(f"获得认证代码失败：{resp}")
    if resp.get("status") != 0:
        raise Exception(f"获得认证代码失败：{resp['msg']}")
    return resp["data"]["code"]


def _get_cred(grant: str) -> dict:
    resp = requests.post(CRED_CODE_URL, json={"code": grant, "kind": 1}, headers=HEADER_LOGIN).json()
    if resp["code"] != 0:
        raise Exception(f"获得cred失败：{resp['message']}")
    return resp["data"]


def _get_binding_list(headers: dict, token: str) -> list:
    v = []
    h = _get_sign_header(BINDING_URL, "get", None, headers.copy(), token)
    resp = requests.get(BINDING_URL, headers=h).json()
    if resp["code"] != 0:
        raise Exception(f"请求角色列表出现问题：{resp['message']}")
    for i in resp["data"]["list"]:
        if i.get("appCode") not in ("arknights", "endfield"):
            continue
        for j in i.get("bindingList"):
            j["appCode"] = i["appCode"]
        v.extend(i["bindingList"])
    return v


def _sign_for_arknights(data: dict, headers: dict, token: str) -> list[str]:
    body = {"gameId": data.get("gameId"), "uid": data.get("uid")}
    url = SIGN_URL_MAPPING["arknights"]
    h = _get_sign_header(url, "post", body, headers.copy(), token)
    resp = requests.post(url, headers=h, json=body).json()
    game_name = data.get("gameName")
    channel = data.get("channelName")
    nickname = data.get("nickName") or ""
    if resp.get("code") != 0:
        return [f"[{game_name}]角色{nickname}({channel})签到失败！原因：{resp['message']}"]
    result = ""
    awards = resp["data"]["awards"]
    for j in awards:
        res = j["resource"]
        result += f"{res['name']}×{j.get('count') or 1}"
    return [f"[{game_name}]角色{nickname}({channel})签到成功，获得了{result}"]


def _sign_for_endfield(data: dict, headers: dict, token: str) -> list[str]:
    roles: list[dict] = data.get("roles", [])
    game_name = data.get("gameName")
    channel = data.get("channelName")
    result_list = []
    for role in roles:
        nickname = role.get("nickname") or ""
        url = SIGN_URL_MAPPING["endfield"]
        h = _get_sign_header(url, "post", None, headers.copy(), token)
        h.update(
            {
                "Content-Type": "application/json",
                "sk-game-role": f"3_{role['roleId']}_{role['serverId']}",
                "referer": "https://game.skland.com/",
                "origin": "https://game.skland.com/",
            }
        )
        resp = requests.post(url, headers=h).json()
        if resp["code"] != 0:
            result_list.append(f"[{game_name}]角色{nickname}({channel})签到失败！原因:{resp['message']}")
        else:
            awards_result = []
            result_data = resp["data"]
            result_info_map = result_data["resourceInfoMap"]
            for a in result_data["awardIds"]:
                award_id = a["id"]
                awards = result_info_map[award_id]
                awards_result.append(f"{awards['name']}×{awards['count']}")
            result_list.append(f"[{game_name}]角色{nickname}({channel})签到成功，获得了:{','.join(awards_result)}")
    return result_list


def do_sign(hg_token: str) -> tuple[bool, list[str]]:
    """
    对一个用户执行签到。
    返回 (是否成功, 日志消息列表)
    """
    try:
        cred_resp = get_cred_by_token(hg_token)
    except Exception as e:
        return False, [f"Token认证失败：{e}"]

    sign_token = cred_resp["token"]
    headers = HEADER.copy()
    headers["cred"] = cred_resp["cred"]

    try:
        characters = _get_binding_list(headers, sign_token)
    except Exception as e:
        return False, [f"获取角色列表失败：{e}"]

    if not characters:
        return False, ["未找到任何绑定角色"]

    all_logs: list[str] = []
    success = True
    for ch in characters:
        app_code = ch["appCode"]
        try:
            if app_code == "arknights":
                msgs = _sign_for_arknights(ch, headers, sign_token)
            elif app_code == "endfield":
                msgs = _sign_for_endfield(ch, headers, sign_token)
            else:
                continue
            all_logs.extend(msgs)
            for m in msgs:
                # 重复签到不算失败，只有真正的错误才算失败
                if "失败" in m and "重复签到" not in m:
                    success = False
        except Exception as e:
            all_logs.append(f"签到异常：{e}")
            success = False

    return success, all_logs
