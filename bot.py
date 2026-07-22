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
    """获取 QQ 机器人的 access_token"""
    url = "https://bots.qq.com/app/getAppAccessToken"
    payload = {"appId": QQ_APPID, "clientSecret": QQ_APPSECRET}
    res = requests.post(url, json=payload)
    return res.json().get("access_token", "")

async def main():
    token = get_access_token()
    if not token:
        print("获取 token 失败，检查 APPID 和 APPSECRET")
        return

    headers = {
        "Authorization": f"QQBot {token}",
        "X-Union-Appid": QQ_APPID
    }

    # 1. 获取网关地址
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.sgroup.qq.com/gateway", headers=headers) as resp:
            data = await resp.json()
            ws_url = data.get("url", "")

    if not ws_url:
        print("获取网关失败")
        return

    print(f"连接网关: {ws_url}")

    # 2. 建立 WebSocket 连接
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url, headers=headers) as ws:
            print("WebSocket 已连接，等待 Hello...")
            heartbeat_interval = 30000  # 默认 30 秒

            async def send_heartbeat():
                while True:
                    await asyncio.sleep(heartbeat_interval / 1000)
                    await ws.send(json.dumps({"op": 1, "d": None}))

            async def identify():
                # 2 号事件：鉴权
                await ws.send_str(json.dumps({...}))
                    "op": 2,
                    "d": {
                        "token": f"QQBot {token}",
                        "intents": (1 << 25) | (1 << 0),  # 群 @ + 私聊
                        "shard": [0, 1]
                    }
                }))

            identified = False
            heartbeat_task = None

            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    break
                data = json.loads(msg.data)
                op = data.get("op")

                # 10: Hello
                if op == 10:
                    heartbeat_interval = data["d"]["heartbeat_interval"]
                    print(f"收到 Hello，心跳间隔: {heartbeat_interval}ms")
                    await identify()
                    identified = True
                    heartbeat_task = asyncio.create_task(send_heartbeat())
                    print("鉴权已发送，等待事件...")

                # 0: 消息事件
                elif op == 0:
                    event_type = data.get("t")
                    event_data = data.get("d", {})

                    if event_type in ("GROUP_AT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"):
                        content = event_data.get("content", "").strip()
                        msg_id = event_data.get("id")
                        print(f"收到消息: {content}")

                        reply = call_llm(content)

                        # 被动回复
                        reply_url = f"https://api.sgroup.qq.com/v2/{( 'channels/' + event_data['channel_id'] ) if event_type == 'GROUP_AT_MESSAGE_CREATE' else 'users/@me/channels'}/messages"
                        # 简化：直接用消息 ID 回复
                        if event_type == "GROUP_AT_MESSAGE_CREATE":
                            post_url = f"https://api.sgroup.qq.com/v2/channels/{event_data['channel_id']}/messages"
                            body = {
                                "content": reply,
                                "msg_id": msg_id
                            }
                        else:
                            # 私聊回复
                            post_url = f"https://api.sgroup.qq.com/v2/users/@me/channels/{event_data.get('author', {}).get('user_openid', '')}/messages"
                            body = {
                                "content": reply,
                                "msg_id": msg_id
                            }

                        try:
                            async with aiohttp.ClientSession() as s:
                                async with s.post(post_url, headers=headers, json=body) as r:
                                    if r.status == 200:
                                        print(f"回复成功: {reply[:20]}...")
                                    else:
                                        print(f"回复失败: {r.status}")
                        except Exception as e:
                            print(f"回复异常: {e}")

                # 7: 服务端要求重连
                elif op == 7:
                    print("服务端要求重连...")
                    break

                # 11: 心跳 ACK
                elif op == 11:
                    pass

            if heartbeat_task:
                heartbeat_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
