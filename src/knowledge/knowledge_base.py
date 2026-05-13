#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
多商家知识库。
保留 TF-IDF 检索，并加入比赛演示所需的“黄金路径”关键词命中。
"""

import json
import os
import uuid
from typing import Dict, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


DEFAULT_MERCHANTS = {
    "tea_shop": {
        "id": "tea_shop",
        "name": "茶语时光",
        "slogan": "鲜果茶饮与轻甜点",
        "accent": "#20d6a4",
        "knowledge": [
            {"id": "tea_1", "question": "你们招牌是什么？", "answer": "我们的招牌是杨枝甘露，使用芒果、西柚和椰奶现做。", "category": "黄金路径"},
            {"id": "tea_2", "question": "营业时间是什么？", "answer": "茶语时光营业时间是 10:00-22:00，周末不打烊。", "category": "黄金路径"},
            {"id": "tea_3", "question": "可以少糖吗？", "answer": "可以，所有饮品都支持正常糖、七分糖、五分糖、三分糖和不另外加糖。", "category": "饮品定制"},
            {"id": "tea_4", "question": "配送范围多远？", "answer": "门店 3 公里内支持外送，高峰期预计 30-45 分钟送达。", "category": "配送"},
        ],
    },
    "book_store": {
        "id": "book_store",
        "name": "墨香阁",
        "slogan": "图书、文创与安静阅读空间",
        "accent": "#8fb7ff",
        "knowledge": [
            {"id": "book_1", "question": "你们招牌是什么？", "answer": "墨香阁的招牌服务是新书推荐和独立作者签名本专区。", "category": "黄金路径"},
            {"id": "book_2", "question": "营业时间是什么？", "answer": "墨香阁营业时间是 09:30-21:30，店内阅读区 21:00 停止入座。", "category": "黄金路径"},
            {"id": "book_3", "question": "可以预订图书吗？", "answer": "可以，提供书名或 ISBN 后，我们会为您查询库存并保留 48 小时。", "category": "图书服务"},
            {"id": "book_4", "question": "有没有会员折扣？", "answer": "会员购买图书享 9 折，文创商品享 95 折，活动书除外。", "category": "会员"},
        ],
    },
}


class KnowledgeBase:
    """按 merchant_id 隔离的真实 JSON 文件知识库。"""

    def __init__(self, knowledge_file: str = "data/knowledge_base.json", merchant_id: str = "tea_shop"):
        self.knowledge_file = knowledge_file
        self.merchants = self.load_knowledge()
        self.merchant_id = self.normalize_merchant_id(merchant_id)
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
        self.question_vectors = None
        self.update_vectors()

    def load_knowledge(self) -> Dict:
        """加载知识库；旧 list 格式会自动迁移为多商家格式。"""
        if not os.path.exists(self.knowledge_file):
            self.save_all(DEFAULT_MERCHANTS)
            return DEFAULT_MERCHANTS.copy()

        try:
            with open(self.knowledge_file, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            data = DEFAULT_MERCHANTS.copy()

        if isinstance(data, list):
            migrated = DEFAULT_MERCHANTS.copy()
            migrated["general_store"] = {
                "id": "general_store",
                "name": "通用商城",
                "slogan": "旧知识库自动迁移",
                "accent": "#f8c66a",
                "knowledge": [self._with_id(item) for item in data],
            }
            self.save_all(migrated)
            return migrated

        if "merchants" in data:
            data = data["merchants"]

        for merchant_id, merchant in DEFAULT_MERCHANTS.items():
            data.setdefault(merchant_id, merchant)
        self.save_all(data)
        return data

    def save_all(self, merchants: Dict) -> None:
        """保存全部商家数据。"""
        directory = os.path.dirname(self.knowledge_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.knowledge_file, "w", encoding="utf-8") as file:
            json.dump({"merchants": merchants}, file, ensure_ascii=False, indent=2)

    def normalize_merchant_id(self, merchant_id: Optional[str]) -> str:
        return merchant_id if merchant_id in self.merchants else "tea_shop"

    def set_merchant(self, merchant_id: str) -> None:
        """切换当前商家，并重建向量。"""
        self.merchant_id = self.normalize_merchant_id(merchant_id)
        self.update_vectors()

    def list_merchants(self) -> List[Dict]:
        return [
            {
                "id": merchant["id"],
                "name": merchant["name"],
                "slogan": merchant.get("slogan", ""),
                "accent": merchant.get("accent", "#20d6a4"),
                "count": len(merchant.get("knowledge", [])),
            }
            for merchant in self.merchants.values()
        ]

    def get_merchant(self, merchant_id: Optional[str] = None) -> Dict:
        merchant_id = self.normalize_merchant_id(merchant_id or self.merchant_id)
        return self.merchants[merchant_id]

    @property
    def knowledge(self) -> List[Dict]:
        return self.get_merchant().setdefault("knowledge", [])

    def update_vectors(self) -> None:
        questions = [item.get("question", "") for item in self.knowledge if item.get("question")]
        self.question_vectors = self.vectorizer.fit_transform(questions) if questions else None

    def query(self, question: str, threshold: float = 0.3, merchant_id: Optional[str] = None) -> Optional[str]:
        result = self.query_with_score(question, merchant_id=merchant_id)
        if result and result["score"] >= threshold:
            return result["answer"]
        return None

    def query_with_score(self, question: str, merchant_id: Optional[str] = None) -> Optional[Dict]:
        """优先黄金路径，再走 TF-IDF。"""
        if merchant_id:
            self.set_merchant(merchant_id)

        golden = self._golden_path(question)
        if golden:
            return golden

        if not self.knowledge or self.question_vectors is None:
            return None

        question_vector = self.vectorizer.transform([question])
        similarities = cosine_similarity(question_vector, self.question_vectors)[0]
        max_index = int(similarities.argmax())
        item = self.knowledge[max_index]
        return {
            "id": item.get("id"),
            "question": item.get("question", ""),
            "answer": item.get("answer", ""),
            "score": float(similarities[max_index]),
            "source": "tfidf",
            "merchant_id": self.merchant_id,
        }

    def add_knowledge(self, question: str, answer: str, merchant_id: Optional[str] = None, category: str = "后台新增") -> Dict:
        """新增知识并实时保存。"""
        if merchant_id:
            self.set_merchant(merchant_id)
        item = {"id": uuid.uuid4().hex[:10], "question": question.strip(), "answer": answer.strip(), "category": category}
        self.knowledge.append(item)
        self.save_all(self.merchants)
        self.update_vectors()
        return item

    def delete_knowledge(self, knowledge_id: str, merchant_id: Optional[str] = None) -> bool:
        """删除指定知识。"""
        if merchant_id:
            self.set_merchant(merchant_id)
        before = len(self.knowledge)
        self.get_merchant()["knowledge"] = [item for item in self.knowledge if item.get("id") != knowledge_id]
        changed = len(self.knowledge) != before
        if changed:
            self.save_all(self.merchants)
            self.update_vectors()
        return changed

    def get_knowledge(self, merchant_id: Optional[str] = None) -> List[Dict]:
        if merchant_id:
            self.set_merchant(merchant_id)
        return self.knowledge

    def _golden_path(self, question: str) -> Optional[Dict]:
        text = question.strip()
        merchant = self.get_merchant()
        rules = [
            (["招牌", "推荐", "必点", "特色"], "招牌"),
            (["营业时间", "几点开", "几点关", "开门", "打烊"], "营业时间"),
        ]
        for keywords, target in rules:
            if any(keyword in text for keyword in keywords):
                for item in merchant.get("knowledge", []):
                    combined = f"{item.get('question', '')} {item.get('answer', '')}"
                    if target in combined:
                        return {
                            "id": item.get("id"),
                            "question": item.get("question", ""),
                            "answer": item.get("answer", ""),
                            "score": 1.0,
                            "source": "golden",
                            "merchant_id": self.merchant_id,
                        }
        return None

    def _with_id(self, item: Dict) -> Dict:
        item = dict(item)
        item.setdefault("id", uuid.uuid4().hex[:10])
        item.setdefault("category", "旧知识")
        return item
