from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)

# ============ 从环境变量读（Render 里设） ============
QQ_APPID = os.environ.get("QQ_APPID", "1904762056")
QQ_APPSECRET = os.environ.get("QQ_APPSECRET", "tGe2RqGg7Y0SvPtOuQxV3cCmNzbEsWBq")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "sk-17e91de636bf49a68eb632cf758fbae1")
# ===============================================

LLM_API_URL = "https://api.openai.com/v1/chat/completions"
LLM_MODEL = "gpt-3.5-turbo"

def get_qq_token():
    url = f"https://api.q.qq.com/api/getToken?grant_type=client_credentials&client_id={QQ_APPID}&client_secret={QQ_APPSECRET}"
    try:
        res = requests.get(url).json()
        return res.get('access_token')
    except Exception as e:
        print("获取Token失败:", e)
        return None

@app.route('/qq_callback', methods=['GET', 'POST'])
def callback():
    if request.method == 'GET':
        return request.args.get('echo', '')

    data = request.json
    print("收到消息:", json.dumps(data, ensure_ascii=False))

    try:
        msg_content = data.get('content', '')
        user_openid = data.get('sender', {}).get('user_openid', '')

        if not msg_content or not user_openid:
            return jsonify({"code": 0})

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"}
        payload = {"model": LLM_MODEL, "messages": [{"role": "user", "content": msg_content}]}
        llm_res = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=30)
        reply_content = llm_res.json()['choices'][0]['message']['content']

        token = get_qq_token()
        if token:
            send_url = f"https://api.q.qq.com/v3/message/private/send?access_token={token}"
            send_data = {"appid": QQ_APPID, "receiver_openid": user_openid, "msg_type": 0, "content": reply_content}
            requests.post(send_url, json=send_data)

    except Exception as e:
        print("处理消息出错:", e)

    return jsonify({"code": 0})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
