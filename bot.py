import asyncio
import os
import requests
import json
import botpy
from botpy.message import Message
from botpy import logging

_log = logging.get_logger()

# ============ 从环境变量读取密钥（Railway 里设） ============
QQ_APPID = os.environ.get("QQ_APPID", "1904762056")
QQ_APPSECRET = os.environ.get("QQ_APPSECRET", "tGe2RqGg7Y0SvPtOuQxV3cCmNzbEsWBq")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "sk-17e91de636bf49a68eb632cf758fbae1")
# ======================================================

LLM_API_URL = "https://api.openai.com/v1/chat/completions"
LLM_MODEL = "gpt-3.5-turbo"

def call_llm(prompt):
    """调用大模型获取回复"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        res = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=30)
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        _log.error(f"LLM 调用失败: {e}")
        return "抱歉，我现在有点累，稍后再试试吧。"

class MyBot(botpy.Client):
    async def on_ready(self):
        _log.info(f"机器人 {self.robot.name} 已上线！")

    async def on_at_message_create(self, message: Message):
        """处理群聊 @ 消息"""
        content = message.content.strip()
        _log.info(f"收到 @ 消息: {content}")
        reply = call_llm(content)
        await message.reply(content=reply)

    async def on_message_create(self, message: Message):
        """处理私聊消息"""
        if not message.group_openid:
            content = message.content.strip()
            _log.info(f"收到私聊消息: {content}")
            reply = call_llm(content)
            await message.reply(content=reply)

if __name__ == "__main__":
    intents = botpy.Intents(
        public_guild_messages=True,
        direct_message=True,
    )
    client = MyBot(intents=intents, is_sandbox=False)
    client.run(appid=QQ_APPID, secret=QQ_APPSECRET)
