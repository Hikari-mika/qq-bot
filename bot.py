import asyncio
import json
import os
import aiohttp
import requests
import gc
import traceback

QQ_APPID = os.environ.get("QQ_APPID", "1904762056")
QQ_APPSECRET = os.environ.get("QQ_APPSECRET", "DjGnLtS1bBmO0dGuYDsYEvdL4nXH2njf")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "sk-17e91de636bf49a68eb632cf758fbae1")

LLM_API_URL = "https://api.openai.com/v1/chat/completions"
LLM_MODEL = "gpt-3.5-turbo"

_cached_token = None
_cached_expire = 0

def get_qq_bot_token():
    global _cached_token, _cached_expire
    import time
    now = time.time()
    if _cached_token and now < _cached_expire - 60:
        return _cached_token
    try:
        print("正在向 QQ 官方请求 Access Token...")
        url = "https://bots.qq.com/app/getAppAccessToken"
        headers = {"Content-Type": "application/json"}
        payload = {"appId": str(QQ_APPID), "clientSecret": str(QQ_APPSECRET)}
        res = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        print(f"HTTP 状态码: {res.status_code}")
        print(f"返回内容: {res.text}")
        data = res.json()
        if data.get("code") == 0:
            _cached_token = data["access_token"]
            _cached_expire = now + int(data.get("expires_in", 7200))
            print(f"Token 获取成功: {_cached_token[:15]}...")
            return _cached_token
        else:
            print(f"Token 获取失败: code={data.get('code')}, message={data.get('message')}")
            return None
    except Exception as e:
        print(f"请求 Token 时发生异常: {e}")
        traceback.print_exc()
        return None

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
    token_str = get_qq_bot_token()
    if not token_str:
        print("无法获取 Token，5秒后重试")
        await asyncio.sleep(5)
        return
    token = f"QQBot {token_str}"
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
                    ready = False
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
                            elif op == 0:
                                t = data.get("t")
                                d = data.get("d", {})
                                if t == "READY":
                                    ready = True
                                    heartbeat_task = asyncio.create_task(send_heartbeat())
                                    print("✅ 鉴权成功，机器人已上线！")
                                elif t in ("GROUP_AT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"):
                                    content = d.get("content", "").strip()
                                    print(f"收到消息: {content[:30]}...")
                                    reply = call_llm(content)
                                    channel_id = d.get("channel_id", "")
                                    user_openid = d.get("author", {}).get("user_openid", "")
                                    if t == "GROUP_AT_MESSAGE_CREATE":
                                        post_url = f"https://api.sgroup.qq.com/v2/channels/{channel_id}/messages"
                                    else:
                                        post_url = f"https://api.sgroup.qq.com/v2/users/@me/channels/{user_openid}/messages"
                                    body = {"content": reply}
                                    try:
                                        async with aiohttp.ClientSession() as s:
                                            await s.post(post_url, headers=headers, json=body, timeout=10)
                                            print("回复成功")
                                    except Exception as e:
                                        print(f"回复异常: {e}")
                            elif op == 7:
                                print("服务端要求重连")
                                break
                            elif op == 9:
                                print(f"鉴权失败! 数据: {data}")
                                break
                        except Exception as loop_err:
                            print(f"消息处理异常: {loop_err}")
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
        print(f"启动失败: {e}")
        traceback.print_exc()
