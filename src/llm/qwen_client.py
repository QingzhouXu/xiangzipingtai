#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
多后端 LLM 客户端。
支持 Ollama 本地模型、DashScope 云端 Qwen 模型和 Mock 兜底。
通过 LLM_BACKEND 环境变量切换：ollama / dashscope / mock。
"""

import json
import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Optional

import requests


class BaseLLMClient(ABC):
    """LLM 客户端抽象基类。"""

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """非流式聊天。"""

    @abstractmethod
    def stream_chat(self, messages: List[Dict[str, str]], **kwargs) -> Iterable[str]:
        """流式聊天，逐块产出文本。"""

    @abstractmethod
    def heartbeat(self) -> Dict:
        """返回模型状态与延迟。"""

    def generate(self, prompt: str, **kwargs) -> str:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)


class QwenOllamaClient(BaseLLMClient):
    """面向 Ollama 的轻量客户端。"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = {
            "ollama_base": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            "model_name": os.getenv("OLLAMA_MODEL", ""),
            "temperature": 0.6,
            "top_p": 0.9,
            "num_predict": 2048,
            "keep_alive": "1h",
            "timeout": 180,
        }
        if config:
            self.config.update(config)
        # 自动检测可用模型
        if not self.config["model_name"]:
            self.config["model_name"] = self._detect_model()

    def _detect_model(self) -> str:
        """检测 Ollama 已安装的模型，优先选中文对话模型。"""
        try:
            resp = requests.get(f"{self.config['ollama_base']}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            if not models:
                return "qwen2.5:1.5b"
            # 优先选择 qwen 系列
            preferred = [m for m in models if "qwen" in m.lower()]
            return preferred[0] if preferred else models[0]
        except Exception:
            return "qwen2.5:1.5b"

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
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
        """真实流式请求，按 chunk 输出，兼容思考/推理模型的输出格式。"""
        payload = self._build_payload(messages, stream=True, kwargs=kwargs)
        try:
            response = requests.post(
                f"{self.config['ollama_base']}/api/chat",
                json=payload,
                timeout=self.config["timeout"],
                stream=True,
            )
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
                if chunk.get("done") and not content:
                    # 思考模型可能只在 message.content 里放内容，done 时才汇总
                    final_content = chunk.get("message", {}).get("content", "")
                    if final_content:
                        yield final_content
        except Exception as exc:
            yield f"\n\n开发板模型连接中断。错误信息：{exc}"

    def heartbeat(self) -> Dict:
        started = time.perf_counter()
        try:
            response = requests.get(f"{self.config['ollama_base']}/api/tags", timeout=3)
            response.raise_for_status()
            latency = int((time.perf_counter() - started) * 1000)
            data = response.json()
            models = [item.get("name", "") for item in data.get("models", [])]
            configured_model = self.config["model_name"]
            model = configured_model if configured_model in models else (models[0] if models else configured_model)
            return {"status": "success", "latency": latency, "model": model, "backend": "ollama"}
        except Exception as exc:
            return {"status": "error", "latency": None, "model": self.config["model_name"], "backend": "ollama", "error": str(exc)}

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
                "think": 0,
            },
        }


class QwenCloudClient(BaseLLMClient):
    """DashScope 云端 Qwen 模型客户端（OpenAI 兼容接口）。"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = {
            "api_key": os.getenv("DASHSCOPE_API_KEY", ""),
            "base_url": os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            "model_name": os.getenv("DASHSCOPE_MODEL", "qwen-plus"),
            "temperature": 0.6,
            "top_p": 0.9,
            "max_tokens": 512,
            "timeout": 120,
        }
        if config:
            self.config.update(config)

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        payload = self._build_payload(messages, stream=False, kwargs=kwargs)
        try:
            response = requests.post(
                f"{self.config['base_url']}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.config["timeout"],
            )
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip() or "模型没有返回内容。"
        except requests.RequestException as exc:
            return f"云端模型暂时不可用，请稍后再试。错误信息：{exc}"
        except (ValueError, KeyError, IndexError) as exc:
            return f"模型返回解析失败：{exc}"

    def stream_chat(self, messages: List[Dict[str, str]], **kwargs) -> Iterable[str]:
        payload = self._build_payload(messages, stream=True, kwargs=kwargs)
        try:
            with requests.post(
                f"{self.config['base_url']}/chat/completions",
                json=payload,
                headers=self._headers(),
                stream=True,
                timeout=self.config["timeout"],
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
        except requests.RequestException as exc:
            yield f"\n\n云端模型连接中断，已保留当前输出。错误信息：{exc}"

    def heartbeat(self) -> Dict:
        started = time.perf_counter()
        try:
            response = requests.get(
                f"{self.config['base_url']}/models",
                headers=self._headers(),
                timeout=5,
            )
            latency = int((time.perf_counter() - started) * 1000)
            if response.status_code == 200:
                return {"status": "success", "latency": latency, "model": self.config["model_name"], "backend": "dashscope"}
            return {"status": "error", "latency": latency, "model": self.config["model_name"], "backend": "dashscope", "error": f"HTTP {response.status_code}"}
        except Exception as exc:
            return {"status": "error", "latency": None, "model": self.config["model_name"], "backend": "dashscope", "error": str(exc)}

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, messages: List[Dict[str, str]], stream: bool, kwargs: Dict) -> Dict:
        config = {**self.config, **kwargs}
        return {
            "model": config["model_name"],
            "messages": messages,
            "stream": stream,
            "temperature": config.get("temperature", 0.6),
            "top_p": config.get("top_p", 0.9),
            "max_tokens": config.get("max_tokens", 512),
        }


class MockQwenClient(BaseLLMClient):
    """测试兜底客户端。"""

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        last_message = messages[-1]["content"]
        return f"这是本地演示兜底回复：{last_message}"

    def stream_chat(self, messages: List[Dict[str, str]], **kwargs) -> Iterable[str]:
        text = self.chat(messages, **kwargs)
        for char in text:
            yield char

    def heartbeat(self) -> Dict:
        return {"status": "success", "latency": 1, "model": "mock-qwen", "backend": "mock"}


_default_client = None


def reset_client() -> None:
    """重置全局 LLM 客户端，允许在运行时切换后端。"""
    global _default_client
    _default_client = None


def get_qwen_client(config: Optional[Dict] = None, use_mock: bool = False, backend: Optional[str] = None) -> BaseLLMClient:
    """获取全局 LLM 客户端。

    后端选择优先级：backend 参数 > LLM_BACKEND 环境变量 > use_mock 参数。
    """
    global _default_client
    if _default_client is None:
        resolved = backend or os.getenv("LLM_BACKEND", "ollama")
        if use_mock or resolved == "mock":
            _default_client = MockQwenClient()
        elif resolved == "dashscope":
            _default_client = QwenCloudClient(config)
        else:
            _default_client = QwenOllamaClient(config)
    return _default_client
