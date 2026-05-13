#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
意图识别模块
负责识别用户的意图
"""

from typing import Dict, Any


class IntentClassifier:
    """意图分类器"""
    
    def __init__(self):
        """初始化意图分类器"""
        # 定义意图映射和关键词
        self.intent_map = {
            "greeting": {
                "keywords": ["你好", "您好", "嗨", "早上好", "下午好", "晚上好", "Hello", "Hi", "哈喽"],
                "confidence": 0.9
            },
            "thanks": {
                "keywords": ["谢谢", "感谢", "多谢", "谢了", "辛苦了", "非常感谢", "太感谢了"],
                "confidence": 0.9
            },
            "goodbye": {
                "keywords": ["再见", "拜拜", "下次见", "先走了", "告辞", "回见"],
                "confidence": 0.9
            },
            "chitchat": {
                "keywords": ["今天天气", "天气怎么样", "吃了吗", "在吗", "忙吗", "最近好吗", "你好", "聊聊天"],
                "confidence": 0.7
            },
            "faq": {
                "keywords": ["如何", "怎样", "什么", "为什么", "哪里", "什么时候", "价格", "费用", "收费",
                            "怎么", "能否", "可以", "需要", "请问", "请教", "帮忙", "解决"],
                "confidence": 0.6
            }
        }
        
        # 定义否定词（用于降低置信度）
        self.negation_words = ["不", "不是", "没有", "别", "勿", "不用"]
    
    def classify(self, text: str) -> Dict[str, Any]:
        """分类用户意图
        
        Args:
            text: 用户输入的文本
            
        Returns:
            dict: 包含intent和confidence的字典
        """
        text = text.strip()
        
        if not text:
            return {"intent": "unknown", "confidence": 0.0}
        
        # 统计每个意图的匹配关键词数量
        intent_scores = {}
        
        for intent, config in self.intent_map.items():
            match_count = 0
            for keyword in config["keywords"]:
                if keyword in text:
                    match_count += 1
            
            if match_count > 0:
                # 计算置信度：基于匹配关键词数量和基础置信度
                max_keywords = len(config["keywords"])
                match_ratio = match_count / max_keywords
                base_confidence = config["confidence"]
                confidence = base_confidence * (0.5 + 0.5 * match_ratio)
                
                # 如果包含否定词，降低置信度
                for neg_word in self.negation_words:
                    if neg_word in text:
                        confidence *= 0.5
                        break
                
                intent_scores[intent] = confidence
        
        if intent_scores:
            # 找到置信度最高的意图
            best_intent = max(intent_scores, key=intent_scores.get)
            best_confidence = intent_scores[best_intent]
            
            return {
                "intent": best_intent,
                "confidence": round(best_confidence, 2),
                "matches": intent_scores
            }
        else:
            # 默认返回faq意图，置信度较低
            return {
                "intent": "faq",
                "confidence": 0.3,
                "matches": {}
            }
    
    def add_intent(self, intent_name: str, keywords: list, confidence: float = 0.7):
        """添加新的意图和关键词
        
        Args:
            intent_name: 意图名称
            keywords: 关键词列表
            confidence: 基础置信度
        """
        self.intent_map[intent_name] = {
            "keywords": keywords,
            "confidence": confidence
        }
    
    def get_intents(self) -> list:
        """获取所有意图
        
        Returns:
            list: 意图列表
        """
        return list(self.intent_map.keys())
    
    def remove_intent(self, intent_name: str):
        """移除意图
        
        Args:
            intent_name: 意图名称
        """
        if intent_name in self.intent_map:
            del self.intent_map[intent_name]
    
    def update_intent(self, intent_name: str, keywords: list = None, confidence: float = None):
        """更新意图配置
        
        Args:
            intent_name: 意图名称
            keywords: 新的关键词列表（可选）
            confidence: 新的置信度（可选）
        """
        if intent_name in self.intent_map:
            if keywords is not None:
                self.intent_map[intent_name]["keywords"] = keywords
            if confidence is not None:
                self.intent_map[intent_name]["confidence"] = confidence


if __name__ == "__main__":
    # 测试意图分类器
    classifier = IntentClassifier()
    
    test_cases = [
        "你好，我想咨询一下",
        "谢谢，问题解决了",
        "再见，下次再聊",
        "今天天气怎么样",
        "如何注册账号",
        "这个商品多少钱"
    ]
    
    for test in test_cases:
        result = classifier.classify(test)
        print(f"输入: {test}")
        print(f"意图: {result['intent']}, 置信度: {result['confidence']}")
        print()
