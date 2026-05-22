import requests
import json

# 换成你的 WiFi IP
url = "http://10.38.209.174:11434/api/chat"
data = {
    "model": "qwen:4b",  # 换成你自己的模型名
    "messages": [{"role": "user", "content": "你好，介绍一下自己"}],
    "stream": True  # 开启流式输出
}

try:
    # 把超时时间拉到 300 秒（5分钟），足够模型加载和推理
    response = requests.post(url, json=data, timeout=300, stream=True)
    print("正在生成回复：\n")
    
    full_response = ""
    # 逐行读取流式响应
    for line in response.iter_lines():
        if line:
            chunk = json.loads(line.decode('utf-8'))
            if chunk.get("message"):
                content = chunk["message"]["content"]
                print(content, end="", flush=True)
                full_response += content
    
    print("\n\n完整回复：", full_response)

except Exception as e:
    print("\n请求出错:", str(e))
