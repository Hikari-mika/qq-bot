import asyncio
import json
import os
import aiohttp
import requests
import gc
import traceback

QQ_APPID = os.environ.get("QQ_APPID", "")
QQ_APPSECRET = os.environ.get("QQ_APPSECRET", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

LLM_API_URL = "https://api.openai.com/v1/chat/completions"
LLM_MODEL = "gpt-3.5-turbo"

def call_llm(prompt):
    try:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"}
        payload = {"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}]}
        res = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=10)
        return res.json()['choices'][0]['message']['content']
    except Exception:
        return "我在呢！"

def clear_memory():
    gc.collect()

async def run_bot():
    token = f"QQBot {QQ_APPID}"
    headers = {"Authorization": token, "X-Union-Appid": QQ_APPID}
    ws_url = "wss://sandbox.api.sgroup.qq.com/websocket"
    print("--- Bot 启动 ---")
    while True:
        try:
            print(f"连接网关: {ws_url}")
            clear_memory()
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url, headers=headers, heartbeat=30) as ws:
                    print("WebSocket 已连接")
                    heartbeat_interval = 41250
                    heartbeat_task = None
                    async def send_heartbeat():
                        while True:
                            await asyncio.sleep(heartbeat_interval / 1000)
                            try:
                                await ws.send_str(json.dumps({"op": 1, "d": None}))
                            except:
                                break
                    async for msg in ws:
                        try:
                            if msg.type != aiohttp.WSMsgType.TEXT:
                                continue
                            data = json.loads(msg.data)
                            op = data.get("op")
                            if op == 10:
                                heartbeat_interval = data["d"]["heartbeat_interval"]
                                print(f"收到 Hello, 心跳间隔: {heartbeat_interval}ms")
                                await ws.send_str(json.dumps({"op": 2, "d": {"token": token, "intents": (1 << 9) | (1 << 0), "shard": [0, 1]}}))
                                print("鉴权已发送")
                                heartbeat_task = asyncio.create_task(send_heartbeat())
                            elif op == 0:
                                t = data.get("t")
                                d = data.get("d", {})
                                if t in ("GROUP_AT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"):
                                    content = d.get("content", "").strip()
                                    msg_id = d.get("id")
                                    print(f"收到消息: {content[:30]}...")
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
                                            async with s.post(post_url, headers=headers, json=body, timeout=10) as r:
                                                if r.status in (200, 204):
                                                    print("回复成功")
                                    except Exception as e:
                                        print(f"回复异常: {e}")
                            elif op == 7:
                                print("服务端要求重连")
                                break
                        except Exception as loop_err:
                            print(f"消息处理异常: {loop_err}")
                            traceback.print_exc()
                    if heartbeat_task:
                        heartbeat_task.cancel()
        except Exception as outer_err:
            print(f"发生严重错误: {outer_err}")
            traceback.print_exc()
        print("5秒后尝试重连...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("程序已停止")
    except Exception as e:
        print(f"无法运行的错误: {e}")
