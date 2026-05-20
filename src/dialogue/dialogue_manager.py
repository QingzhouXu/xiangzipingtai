#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对话管理器。
保持原有 DialogueManager 入口，新增多商家、真实 RAG 和 LLM 流式输出能力。
"""

from typing import Dict, Iterable, List, Optional

from knowledge.knowledge_base import KnowledgeBase
from llm.qwen_client import get_qwen_client, reset_client


class DialogueManager:
    """智能客服对话管理器。"""

    def __init__(self, use_mock_llm: bool = False, backend: Optional[str] = None):
        self.knowledge_base = KnowledgeBase()
        self.llm_client = get_qwen_client(use_mock=use_mock_llm, backend=backend)
        self.knowledge_threshold = 0.18
        self.reset_dialogue()

    def reset_dialogue(self, merchant_id: Optional[str] = None) -> None:
        """重置当前或全部演示上下文。"""
        if not hasattr(self, "sessions"):
            self.sessions = {}
        if merchant_id:
            self.sessions[self._session_key(merchant_id)] = []
        else:
            self.sessions = {}
        self.dialogue_history = []
        self.last_knowledge_answer = None

    def process_input(self, user_input: str, merchant_id: str = "tea_shop") -> str:
        """非流式处理，兼容旧接口。"""
        merchant_id = self.knowledge_base.normalize_merchant_id(merchant_id)
        history = self._history(merchant_id)
        history.append({"role": "user", "content": user_input})
        response = self.generate_response(user_input, merchant_id)
        history.append({"role": "assistant", "content": response})
        self.dialogue_history = history
        return response

    def stream_input(self, user_input: str, merchant_id: str = "tea_shop") -> Iterable[str]:
        """真实 SSE 流式处理；始终调用大模型，知识库仅作参考上下文。"""
        merchant_id = self.knowledge_base.normalize_merchant_id(merchant_id)
        history = self._history(merchant_id)
        history.append({"role": "user", "content": user_input})

        rag = self.knowledge_base.query_with_score(user_input, merchant_id=merchant_id)
        messages = self._build_messages(user_input, merchant_id, rag)
        chunks: List[str] = []
        for chunk in self.llm_client.stream_chat(messages):
            chunks.append(chunk)
            yield chunk
        answer = "".join(chunks).strip()
        history.append({"role": "assistant", "content": answer or "模型未返回内容，请再试一次。"})
        self.dialogue_history = history

    def generate_response(self, user_input: str, merchant_id: str = "tea_shop") -> str:
        """始终调用大模型，知识库仅作参考上下文。"""
        rag = self.knowledge_base.query_with_score(user_input, merchant_id=merchant_id)
        return self.llm_client.chat(self._build_messages(user_input, merchant_id, rag))

    def rag_test(self, question: str, merchant_id: str = "tea_shop") -> Dict:
        """后台 RAG 测试接口。"""
        result = self.knowledge_base.query_with_score(question, merchant_id=merchant_id)
        if not result:
            return {"hit": False, "message": "未命中知识库", "merchant_id": merchant_id}
        return {"hit": result["score"] >= self.knowledge_threshold, **result}

    def get_dialogue_history(self, merchant_id: str = "tea_shop") -> List[Dict]:
        return self._history(merchant_id)

    def get_context(self) -> Dict:
        return {"sessions": self.sessions}

    def set_knowledge_threshold(self, threshold: float) -> None:
        self.knowledge_threshold = threshold

    def switch_backend(self, backend: str) -> dict:
        """运行时切换 LLM 后端。返回新后端的心跳状态。"""
        reset_client()
        self.llm_client = get_qwen_client(backend=backend)
        return self.llm_client.heartbeat()

    def _build_messages(self, user_input: str, merchant_id: str, rag: Optional[Dict]) -> List[Dict[str, str]]:
        merchant = self.knowledge_base.get_merchant(merchant_id)
        rag_text = rag["answer"] if rag else "当前问题未明确命中知识库，请基于商家身份给出简洁、诚实的客服回复。"

        persona = merchant.get("persona")
        if persona and persona.get("name"):
            persona_block = (
                f"你的名字是{persona['name']}，是{merchant['name']}的 AI 客服。"
                f"{persona.get('description', '')}"
                "请使用符合这个身份的语气和风格回复。"
            )
        else:
            persona_block = f"你是{merchant['name']}的 AI 客服。"

        system_prompt = (
            f"{persona_block}"
            "请使用中文，回答要简洁、准确、像真实客服。"
            "如果知识库中没有明确依据，不要编造价格、库存或承诺。"
            "可以使用 Markdown 列表、表格和加粗来提升可读性。"
            f"\n\n当前 RAG 参考：{rag_text}"
        )
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._history(merchant_id)[-6:])
        messages.append({"role": "user", "content": user_input})
        return messages

    def _history(self, merchant_id: str) -> List[Dict]:
        key = self._session_key(merchant_id)
        self.sessions.setdefault(key, [])
        return self.sessions[key]

    def _session_key(self, merchant_id: str) -> str:
        return self.knowledge_base.normalize_merchant_id(merchant_id)
