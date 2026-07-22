import asyncio
import json
import os
import aiohttp
import requests

QQ_APPID = os.environ.get("QQ_APPID", "")
QQ_APPSECRET = os.environ.get("QQ_APPSECRET", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

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

def get_access_token():
    url = "https://bots.qq.com/app/getAppAccessToken"
    payload = {"appId": QQ_APPID, "clientSecret": QQ_APPSECRET}
    res = requests.post(url, json=payload)
    return res.json().get("access_token", "")

async def main():
    token = get_access_token()
    if not token:
        print("获取 token 失败")
        return

    headers = {
        "Authorization": f"QQBot {token}",
        "X-Union-Appid": QQ_APPID
    }

    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.sgroup.qq.com/gateway", headers=headers) as resp:
            data = await resp.json()
            ws_url = data.get("url", "")

    if not ws_url:
        print("获取网关失败")
        return

    print(f"连接网关: {ws_url}")

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url, headers=headers) as ws:
            print("WebSocket 已连接")
            heartbeat_interval = 45000
            identified = False
            heartbeat_task = None

            async def send_heartbeat():
                while True:
                    await asyncio.sleep(heartbeat_interval / 1000)
                    await ws.send_str(json.dumps({"op": 1, "d": None}))

            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    break
                data = json.loads(msg.data)
                op = data.get("op")

                if op == 10:
                    heartbeat_interval = data["d"]["heartbeat_interval"]
                    print(f"收到 Hello, 心跳间隔: {heartbeat_interval}ms")
                    await ws.send_str(json.dumps({
                        "op": 2,
                        "d": {
                            "token": f"QQBot {token}",
                            "intents": (1 << 9) | (1 << 15),
                            "shard": [0, 1]
                        }
                    }))
                    identified = True
                    heartbeat_task = asyncio.create_task(send_heartbeat())
                    print("鉴权已发送")

                elif op == 0:
                    t = data.get("t")
                    d = data.get("d", {})
                    if t in ("GROUP_AT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"):
                        content = d.get("content", "").strip()
                        msg_id = d.get("id")
                        print(f"收到消息: {content}")
                        reply = call_llm(content)
                        channel_id = d.get("channel_id", "")
                        user_openid = d.get("author", {}).get("user_openid", "")
                        if t == "GROUP_AT_MESSAGE_CREATE":
                            post_url = f"https://api.sgroup.qq.com/v2/channels/{channel_id}/messages"
                        else:
                            post_url = f"https://api.sgroup.qq.com/v2/users/@me/channels/{user_openid}/messages"
                        body = {"content": reply, "msg_id": msg_id}
                        try:
                            async with aiohttp.ClientSession() as s:
                                async with s.post(post_url, headers=headers, json=body) as r:
                                    if r.status == 204:
                                        print(f"回复成功: {reply[:20]}...")
                                    else:
                                        print(f"回复失败: {r.status}")
                        except Exception as e:
                            print(f"回复异常: {e}")

                elif op == 7:
                    print("要求重连")
                    break

            if heartbeat_task:
                heartbeat_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
