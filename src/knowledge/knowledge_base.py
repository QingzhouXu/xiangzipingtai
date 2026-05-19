#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
多商家常见问题库。
使用 JSON 文件持久化，保留 TF-IDF 检索和演示稳定命中规则。
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
        "name": "星巴克（中关村旗舰店）",
        "slogan": "精品咖啡 · 轻食甜点 · 生活服务",
        "category": "餐饮",
        "rating": "4.9",
        "hours": "08:00 - 22:00",
        "address": "北京市海淀区中关村大街1号",
        "cover": "/static/img/shops/coffee_shop.png",
        "avatar": "/static/img/shops/avatar-cafe.svg",
        "accent": "#ff5a00",
        "persona": {
            "name": "咖啡师小星",
            "description": "亲切专业的咖啡顾问，熟悉每款饮品的风味特点，善于根据顾客口味推荐。说话温和有礼，像朋友一样自然。",
            "avatar": "☕",
        },
        "knowledge": [
            {
                "id": "tea_1",
                "question": "你们招牌是什么？",
                "answer": "本店推荐焦糖玛奇朵、拿铁和杨枝甘露风味特调，第一次到店可以优先尝试焦糖玛奇朵。",
                "category": "招牌推荐",
            },
            {
                "id": "tea_2",
                "question": "营业时间是什么？",
                "answer": "本店营业时间是 08:00 - 22:00，周末正常营业。",
                "category": "门店信息",
            },
            {
                "id": "tea_3",
                "question": "可以外送吗？",
                "answer": "门店 3 公里内支持外送，高峰期预计 30-45 分钟送达。",
                "category": "配送服务",
            },
            {
                "id": "tea_4",
                "question": "有没有会员优惠？",
                "answer": "会员可享积分累计、生日礼和部分饮品专属优惠，具体以门店活动为准。",
                "category": "会员服务",
            },
        ],
    },
    "book_store": {
        "id": "book_store",
        "name": "墨香阁书店",
        "slogan": "图书文创 · 安静阅读空间",
        "category": "生活服务",
        "rating": "4.8",
        "hours": "09:30 - 21:30",
        "address": "北京市海淀区学院路88号",
        "cover": "/static/img/shops/book_store.png",
        "avatar": "/static/img/shops/avatar-book.svg",
        "accent": "#ff5a00",
        "persona": {
            "name": "书童墨墨",
            "description": "温文尔雅的阅读向导，对书籍分类和文创产品了如指掌，像老朋友一样推荐好书。说话文雅有书卷气。",
            "avatar": "📚",
        },
        "knowledge": [
            {
                "id": "book_1",
                "question": "你们招牌是什么？",
                "answer": "墨香阁的特色是新书推荐、独立作者签名本专区和文创礼物搭配服务。",
                "category": "特色服务",
            },
            {
                "id": "book_2",
                "question": "营业时间是什么？",
                "answer": "墨香阁营业时间是 09:30 - 21:30，店内阅读区 21:00 停止入座。",
                "category": "门店信息",
            },
            {
                "id": "book_3",
                "question": "可以预订图书吗？",
                "answer": "可以，提供书名或 ISBN 后，我们会为您查询库存并保留 48 小时。",
                "category": "图书服务",
            },
            {
                "id": "book_4",
                "question": "会员有什么优惠？",
                "answer": "会员购买图书享 9 折，文创商品享 95 折，活动书除外。",
                "category": "会员服务",
            },
        ],
    },
    "beauty_shop": {
        "id": "beauty_shop",
        "name": "云朵甜品店",
        "slogan": "造型护理 · 预约服务",
        "category": "生活服务",
        "rating": "4.9",
        "hours": "10:00 - 21:00",
        "address": "北京市朝阳区望京西路66号",
        "cover": "/static/img/shops/beauty_shop.png",
        "avatar": "/static/img/shops/avatar-salon.svg",
        "accent": "#ff5a00",
        "persona": {
            "name": "甜品师甜甜",
            "description": "甜美活泼的甜品达人，热爱分享每一款甜品的制作故事和口味搭配。说话温暖治愈，让人心情愉悦。",
            "avatar": "🍰",
        },
        "knowledge": [
            {
                "id": "beauty_1",
                "question": "你们招牌是什么？",
                "answer": "本店招牌项目是头皮护理、日常通勤剪发和自然卷造型设计。",
                "category": "招牌项目",
            },
            {
                "id": "beauty_2",
                "question": "营业时间是什么？",
                "answer": "营业时间是 10:00 - 21:00，建议提前预约。",
                "category": "门店信息",
            },
        ],
    },
}


class KnowledgeBase:
    """按 merchant_id 隔离的常见问题库。"""

    def __init__(self, knowledge_file: str = "data/knowledge_base.json", merchant_id: str = "tea_shop"):
        self.knowledge_file = knowledge_file
        self.merchants = self.load_knowledge()
        self.merchant_id = self.normalize_merchant_id(merchant_id)
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
        self.question_vectors = None
        self.update_vectors()

    def load_knowledge(self) -> Dict:
        if not os.path.exists(self.knowledge_file):
            self.save_all(DEFAULT_MERCHANTS)
            return json.loads(json.dumps(DEFAULT_MERCHANTS, ensure_ascii=False))

        try:
            with open(self.knowledge_file, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            data = {"merchants": DEFAULT_MERCHANTS}

        if isinstance(data, list):
            data = {"merchants": {"tea_shop": {**DEFAULT_MERCHANTS["tea_shop"], "knowledge": [self._with_id(item) for item in data]}}}

        merchants = data.get("merchants", data)
        for merchant_id, merchant in DEFAULT_MERCHANTS.items():
            merchants.setdefault(merchant_id, merchant)
            for key, value in merchant.items():
                if key != "knowledge":
                    merchants[merchant_id].setdefault(key, value)
        self.save_all(merchants)
        return merchants

    def save_all(self, merchants: Dict) -> None:
        directory = os.path.dirname(self.knowledge_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.knowledge_file, "w", encoding="utf-8") as file:
            json.dump({"merchants": merchants}, file, ensure_ascii=False, indent=2)

    def normalize_merchant_id(self, merchant_id: Optional[str]) -> str:
        return merchant_id if merchant_id in self.merchants else "tea_shop"

    def set_merchant(self, merchant_id: str) -> None:
        self.merchant_id = self.normalize_merchant_id(merchant_id)
        self.update_vectors()

    def list_merchants(self) -> List[Dict]:
        return [
            {
                "id": merchant["id"],
                "name": merchant["name"],
                "slogan": merchant.get("slogan", ""),
                "category": merchant.get("category", "生活服务"),
                "rating": merchant.get("rating", "4.9"),
                "hours": merchant.get("hours", ""),
                "address": merchant.get("address", ""),
                "cover": merchant.get("cover", ""),
                "avatar": merchant.get("avatar", ""),
                "accent": merchant.get("accent", "#ff5a00"),
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
        if merchant_id:
            self.set_merchant(merchant_id)

        golden = self._stable_hit(question)
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
            "source": "similar",
            "merchant_id": self.merchant_id,
        }

    def add_knowledge(self, question: str, answer: str, merchant_id: Optional[str] = None, category: str = "常见问题") -> Dict:
        if merchant_id:
            self.set_merchant(merchant_id)
        item = {"id": uuid.uuid4().hex[:10], "question": question.strip(), "answer": answer.strip(), "category": category}
        self.knowledge.append(item)
        self.save_all(self.merchants)
        self.update_vectors()
        return item

    def delete_knowledge(self, knowledge_id: str, merchant_id: Optional[str] = None) -> bool:
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

    def _stable_hit(self, question: str) -> Optional[Dict]:
        text = question.strip()
        rules = [
            (["招牌", "推荐", "必点", "特色"], "招牌"),
            (["营业时间", "几点开", "几点关", "开门", "打烊"], "营业时间"),
            (["会员", "优惠", "折扣"], "会员"),
            (["外送", "配送", "送达"], "配送"),
        ]
        for keywords, target in rules:
            if any(keyword in text for keyword in keywords):
                for item in self.knowledge:
                    combined = f"{item.get('question', '')} {item.get('answer', '')} {item.get('category', '')}"
                    if target in combined:
                        return {
                            "id": item.get("id"),
                            "question": item.get("question", ""),
                            "answer": item.get("answer", ""),
                            "score": 1.0,
                            "source": "stable",
                            "merchant_id": self.merchant_id,
                        }
        return None

    def _with_id(self, item: Dict) -> Dict:
        item = dict(item)
        item.setdefault("id", uuid.uuid4().hex[:10])
        item.setdefault("category", "常见问题")
        return item
