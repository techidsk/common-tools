import ast
import base64
import hashlib
import hmac
import json
import os
import time

import httpx
from dotenv import load_dotenv
from loguru import logger

# 在模块开始时就加载 .env 文件
load_dotenv()

PROD_HOOK_URL = os.getenv("FEISHU_BOT_HOOK_URL")
SECRET = os.getenv("FEISHU_SECRET")
assert PROD_HOOK_URL and SECRET, "FEISHU_BOT_HOOK_URL and FEISHU_SECRET must be set"

def gen_sign():
    # 拼接timestamp和secret
    timestamp = int(time.time())

    string_to_sign = "{}\n{}".format(timestamp, SECRET)
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()

    # 对结果进行base64处理
    sign = base64.b64encode(hmac_code).decode("utf-8")

    return sign, timestamp


def send_message_to_feishu(
    params: str | dict, error_info: str | dict | None = None
):
    """
    发送到飞书机器人，
    Args:
        params: str | dict: 参数
        error_info: str | dict: 错误信息

    """
    sign, timestamp = gen_sign()
    if isinstance(params, str):
        main_title = params
    elif isinstance(params, dict):
        task_id = params["task_id"]
        sub_task_id = params["sub_task_id"]
        request_id = params["request_id"]
        main_title = (
            f"任务[{task_id}]-子任务[{sub_task_id}]-请求ID[{request_id}] 出现异常"
        )

    content = ""
    error_msg = ""
    raw_msg = ""
    if isinstance(error_info, str):
        content = error_info
    elif isinstance(error_info, dict):
        content = error_info.get("content", "")
        error_msg = error_info.get("error_msg", "")
        raw_msg = error_info.get("raw", "")

    r = format_str_to_json_style(raw_msg)

    elements = [
        {
            "tag": "div",
            "text": {
                "content": f"**内容**: {content}",
                "tag": "lark_md",
            },
        }
    ]

    if error_msg:
        elements.append(
            {
                "tag": "div",
                "text": {
                    "content": f"**{error_msg}**",
                    "tag": "lark_md",
                },
            }
        )

    if raw_msg:
        elements.append(
            {
                "tag": "markdown",
                "content": f"{r}",
            }
        )

    data = {
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": "interactive",
        "card": {
            "elements": elements,
            "header": {
                "title": {
                    "content": main_title,
                    "tag": "plain_text",
                }
            },
        },
    }

    response = httpx.post(PROD_HOOK_URL, json=data)

    if response.status_code != 200:
        logger.info(response.json())


def format_str_to_json_style(input_str: str | dict) -> str:
    try:
        if isinstance(input_str, dict):
            return json.dumps(input_str, indent=4)

        # d = eval(input_str.strip())
        d = ast.literal_eval(input_str.strip() or "{}")

        pretty_json_str = json.dumps(d, indent=4)

        return pretty_json_str
    except Exception as e:
        logger.error(f"格式化字符串失败: {e}")
        logger.error(input_str)
