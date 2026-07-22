import asyncio
import json
import os
import aiohttp
import requests
import gc
import traceback

QQ_APPID = os.environ.get("QQ_APPID", "")
# 如果鉴权失败，可以尝试把 QQ_APPID 前面加上 Bearer 试试
# QQ_APPID = "Bearer " + os.environ.get("QQ_APPID", "") 

def call_llm(prompt):
    # 为了防止 OpenAI 报错导致整个机器人挂掉，这里也加上保护伞
    try:
        # 如果你还没有 OpenAI Key，把下面的代码注释掉，直接 return 一个固定字符串
        # headers = {"Content-Type": "application/json", "Authorization": f"Bearer sk-你的Key"}
        # payload = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}]}
        # res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
        # return res.json()['choices'][0]['message']['content']
        
        # 临时方案：直接复读，防止外部 API 拖垮机器人
        return "你好！我收到你的消息了：" + prompt[:10] 
    except Exception as e:
        return "抱歉，我现在脑子卡壳了。"

def clear_memory():
    gc.collect()

async def run_bot():
    print("=" * 30)
    print("机器人启动中...")
    
    # 前置检查
    if not QQ_APPID:
        print("❌❌❌ 致命错误：环境变量 QQ_APPID 为空！请去 Railway 设置变量！")
        while True:
            await asyncio.sleep(3600) # 死循环等待，防止反复重启刷屏

    # 这里的 token 格式如果 401，请改成 "Bearer " + QQ_APPID.strip()
    token = f"QQBot {QQ_APPID.strip()}" 
    headers = {
        "Authorization": token,
        "X-Union-Appid": QQ_APPID.strip()
    }
    
    # 确认是沙箱环境
    ws_url = "wss://sandbox.api.sgroup.qq.com/websocket"
    print(f"目标网关: {ws_url}")
    print(f"使用的Token: {token[:15]}...") # 打印前15位看看对不对
    
    while True:
        try:
            clear_memory()
            async with aiohttp.ClientSession() as session:
                print("尝试连接 WebSocket...")
                async with session.ws_connect(ws_url, headers=headers, heartbeat=30, timeout=10) as ws:
                    print("✅ WebSocket 物理连接成功！")
                    
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
                                print(f"📡 收到 Hello 包, 心跳间隔: {heartbeat_interval}ms")
                                
                                # 发送鉴权
                                auth_data = {
                                    "op": 2,
                                    "d": {
                                        "token": token,
                                        "intents": (1 << 9) | (1 << 0), # 群@和私聊
                                        "shard": [0, 1]
                                    }
                                }
                                print(f"🚀 发送鉴权: {auth_data}")
                                await ws.send_str(json.dumps(auth_data))
                                print("✅ 鉴权包已发出，等待服务器回应...")
                                heartbeat_task = asyncio.create_task(send_heartbeat())

                            elif op == 0:
                                t = data.get("t")
                                d = data.get("d", {})
                                
                                if t in ("GROUP_AT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"):
                                    content = d.get("content", "").strip()
                                    user_openid = d.get("author", {}).get("user_openid", "未知用户")
                                    print(f"💬 收到消息 | 用户: {user_openid} | 内容: {content}")
                                    
                                    reply = call_llm(content)
                                    
                                    # 简单的发消息逻辑
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
                                            print(f"📤 回复成功")
                                    except Exception as e:
                                        print(f"❌ 回复异常: {e}")

                            elif op == 7:
                                print("⚠️ 服务器要求重连 (Opcode 7)")
                                break
                                
                            elif op == 9:
                                # 这是一个关键！Opcode 9 代表鉴权失败或者需要重新鉴权
                                print(f"❌❌❌ 收到 Opcode 9 (鉴权失败或被踢出)! 数据: {data}")
                                break

                        except Exception as loop_err:
                            print(f"⚠️ 消息处理内部错误: {loop_err}")
                            # traceback.print_exc() # 调试时可以解开

                    if heartbeat_task:
                        heartbeat_task.cancel()

        except Exception as outer_err:
            # 这里是兜底的最外层错误捕获
            print(f"🔥🔥🔥 发生严重未知错误: {outer_err}")
            # 打印详细堆栈，这对找 bug 至关重要！
            traceback.print_exc()
        
        # 等待 5 秒重连
        print("连接断开，5秒后进行重连...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("程序已停止")
    except Exception as e:
        print(f"启动失败: {e}")
        traceback.print_exc()
