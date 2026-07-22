import asyncio
import json
import os
import aiohttp
import requests

QQ_APPID = os.environ.get("QQ_APPID", "1904762056")
QQ_APPSECRET = os.environ.get("QQ_APPSECRET", "tGe2RqGg7Y0SvPtOuQxV3cCmNzbEsWBq")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "sk-17e91de636bf49a68eb632cf758fbae1")

LLM_API_URL = "https://api.openai.com/v1/chat/completions"
LLM_MODEL = "gpt-3.5-turbo"

def call_llm(prompt):
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"}
    payload = {"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}]}
    try:
        res = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=30)
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"LLM error: {e}")
        return "抱歉，我现在有点累，稍后再试试吧。"

async def handle_message(ws, data):
    print(f"收到消息: {data}")
    content = data.get('d', {}).get('content', '你好')
    reply = call_llm(content)
    await ws.send(json.dumps({
        "op": 0,
        "d": {
            "content": reply
        }
    }))

async def main():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.sgroup.qq.com/gateway/bot?appid={QQ_APPID}&secret={QQ_APPSECRET}") as resp:
            gateway = await resp.json()
            ws_url = gateway.get("url", "")
    if not ws_url:
        print("获取 gateway 失败")
        return
    print(f"连接 WebSocket: {ws_url}")
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            print("WebSocket 已连接")
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("op") == 10:
                        continue
                    if data.get("op") == 0:
                        await handle_message(ws, data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break

if __name__ == "__main__":
    asyncio.run(main())

