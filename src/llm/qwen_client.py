#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ollama / Qwen 客户端。
使用 requests 真实请求本机 Ollama，不依赖 HuggingFace，本项目演示时更轻、更稳。
"""

import json
import os
import time
from typing import Dict, Iterable, List, Optional

import requests


class QwenClient:
    """面向 Ollama 的轻量客户端，保留 QwenClient 类名以兼容旧代码。"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = {
            "ollama_base": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            "model_name": os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b"),
            "temperature": 0.6,
            "top_p": 0.9,
            "num_predict": 512,
            "keep_alive": "1h",
            "timeout": 120,
        }
        if config:
            self.config.update(config)

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """非流式聊天，用于普通 API 或兜底逻辑。"""
        payload = self._build_payload(messages, stream=False, kwargs=kwargs)
        try:
            response = requests.post(
                f"{self.config['ollama_base']}/api/chat",
                json=payload,
                timeout=self.config["timeout"],
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "").strip() or "模型没有返回内容。"
        except requests.RequestException as exc:
            return f"开发板模型暂时不可用，请稍后再试。错误信息：{exc}"
        except ValueError as exc:
            return f"模型返回解析失败：{exc}"

    def stream_chat(self, messages: List[Dict[str, str]], **kwargs) -> Iterable[str]:
        """SSE 使用的真实流式聊天，逐块产出 Ollama 返回的内容。"""
        payload = self._build_payload(messages, stream=True, kwargs=kwargs)
        try:
            with requests.post(
                f"{self.config['ollama_base']}/api/chat",
                json=payload,
                stream=True,
                timeout=self.config["timeout"],
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if data.get("done"):
                        break
        except requests.RequestException as exc:
            yield f"\n\n开发板模型连接中断，已保留当前输出。错误信息：{exc}"

    def heartbeat(self) -> Dict:
        """检测 Ollama /api/tags，返回模型状态与延迟。"""
        started = time.perf_counter()
        try:
            response = requests.get(f"{self.config['ollama_base']}/api/tags", timeout=3)
            response.raise_for_status()
            latency = int((time.perf_counter() - started) * 1000)
            data = response.json()
            models = [item.get("name", "") for item in data.get("models", [])]
            configured_model = self.config["model_name"]
            model = configured_model if configured_model in models else (models[0] if models else configured_model)
            return {"status": "success", "latency": latency, "model": model}
        except Exception as exc:
            return {"status": "error", "latency": None, "model": self.config["model_name"], "error": str(exc)}

    def generate(self, prompt: str, **kwargs) -> str:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def _build_payload(self, messages: List[Dict[str, str]], stream: bool, kwargs: Dict) -> Dict:
        config = {**self.config, **kwargs}
        return {
            "model": config["model_name"],
            "messages": messages,
            "stream": stream,
            "keep_alive": config.get("keep_alive", "1h"),
            "options": {
                "temperature": config.get("temperature", 0.6),
                "top_p": config.get("top_p", 0.9),
                "num_predict": config.get("num_predict", 512),
            },
        }


class MockQwenClient(QwenClient):
    """测试兜底客户端。正式 app.py 默认不会启用 mock。"""

    def __init__(self):
        super().__init__()

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        last_message = messages[-1]["content"]
        return f"这是本地演示兜底回复：{last_message}"

    def stream_chat(self, messages: List[Dict[str, str]], **kwargs) -> Iterable[str]:
        text = self.chat(messages, **kwargs)
        for char in text:
            yield char

    def heartbeat(self) -> Dict:
        return {"status": "success", "latency": 1, "model": "mock-qwen"}


_default_client = None


def get_qwen_client(config: Optional[Dict] = None, use_mock: bool = False) -> QwenClient:
    """获取全局客户端，兼容旧项目调用方式。"""
    global _default_client
    if _default_client is None:
        _default_client = MockQwenClient() if use_mock else QwenClient(config)
    return _default_client
