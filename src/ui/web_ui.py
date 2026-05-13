#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Flask Web 层。
提供用户端、商家后台、SSE 流式聊天、Ollama 心跳和知识库管理 API。
"""

import json
import os
from typing import Dict

from flask import Flask, Response, jsonify, render_template, request, stream_with_context


class WebUI:
    """Web 应用封装。"""

    def __init__(self, dialogue_manager, port: int = 5000):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_dir = os.path.join(project_root, "src", "ui", "templates")
        static_dir = os.path.join(project_root, "src", "ui", "static")
        self.app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
        self.dialogue_manager = dialogue_manager
        self.port = port
        self.register_routes()

    def register_routes(self) -> None:
        @self.app.route("/")
        def index():
            merchant_id = request.args.get("merchant")
            merchants = self.dialogue_manager.knowledge_base.list_merchants()
            merchant = self.dialogue_manager.knowledge_base.get_merchant(merchant_id) if merchant_id else None
            return render_template("index.html", merchants=merchants, merchant=merchant)

        @self.app.route("/chat")
        def chat_page():
            merchant_id = request.args.get("merchant", "tea_shop")
            merchants = self.dialogue_manager.knowledge_base.list_merchants()
            merchant = self.dialogue_manager.knowledge_base.get_merchant(merchant_id)
            return render_template("index.html", merchants=merchants, merchant=merchant)

        @self.app.route("/admin")
        def admin():
            merchants = self.dialogue_manager.knowledge_base.list_merchants()
            return render_template("admin.html", merchants=merchants)

        @self.app.route("/api/chat", methods=["POST"])
        def chat_api():
            data = request.get_json(silent=True) or {}
            message = (data.get("message") or "").strip()
            merchant_id = data.get("merchant_id") or data.get("merchant") or "tea_shop"
            if not message:
                return jsonify({"error": "消息不能为空"}), 400
            try:
                response = self.dialogue_manager.process_input(message, merchant_id=merchant_id)
                return jsonify({"response": response})
            except Exception as exc:
                return jsonify({"error": f"聊天处理失败：{exc}"}), 500

        @self.app.route("/api/chat/stream", methods=["POST"])
        def chat_stream():
            data = request.get_json(silent=True) or {}
            message = (data.get("message") or "").strip()
            merchant_id = data.get("merchant_id") or data.get("merchant") or "tea_shop"
            if not message:
                return jsonify({"error": "消息不能为空"}), 400

            def event_stream():
                try:
                    for chunk in self.dialogue_manager.stream_input(message, merchant_id=merchant_id):
                        yield self._sse("message", {"content": chunk})
                    yield self._sse("done", {"ok": True})
                except Exception as exc:
                    yield self._sse("error", {"message": f"流式输出中断：{exc}"})
                    yield self._sse("done", {"ok": False})

            return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

        @self.app.route("/api/reset", methods=["POST"])
        def reset():
            data = request.get_json(silent=True) or {}
            merchant_id = data.get("merchant_id") or data.get("merchant")
            self.dialogue_manager.reset_dialogue(merchant_id=merchant_id)
            return jsonify({"success": True, "message": "演示对话已重置"})

        @self.app.route("/api/history")
        def history():
            merchant_id = request.args.get("merchant", "tea_shop")
            return jsonify({"history": self.dialogue_manager.get_dialogue_history(merchant_id)})

        @self.app.route("/api/heartbeat")
        def heartbeat():
            return jsonify(self.dialogue_manager.llm_client.heartbeat())

        @self.app.route("/api/merchants")
        def merchants():
            return jsonify({"merchants": self.dialogue_manager.knowledge_base.list_merchants()})

        @self.app.route("/api/knowledge")
        def knowledge_list():
            merchant_id = request.args.get("merchant", "tea_shop")
            kb = self.dialogue_manager.knowledge_base
            merchant = kb.get_merchant(merchant_id)
            return jsonify({"merchant": merchant, "knowledge": kb.get_knowledge(merchant["id"])})

        @self.app.route("/api/knowledge", methods=["POST"])
        def knowledge_add():
            data = request.get_json(silent=True) or {}
            merchant_id = data.get("merchant_id") or "tea_shop"
            question = (data.get("question") or "").strip()
            answer = (data.get("answer") or "").strip()
            if not question or not answer:
                return jsonify({"error": "问题和回答不能为空"}), 400
            item = self.dialogue_manager.knowledge_base.add_knowledge(question, answer, merchant_id=merchant_id)
            return jsonify({"success": True, "item": item})

        @self.app.route("/api/knowledge/<knowledge_id>", methods=["DELETE"])
        def knowledge_delete(knowledge_id):
            merchant_id = request.args.get("merchant", "tea_shop")
            deleted = self.dialogue_manager.knowledge_base.delete_knowledge(knowledge_id, merchant_id=merchant_id)
            return jsonify({"success": deleted})

        @self.app.route("/api/rag/test", methods=["POST"])
        def rag_test():
            data = request.get_json(silent=True) or {}
            merchant_id = data.get("merchant_id") or "tea_shop"
            question = (data.get("question") or "").strip()
            if not question:
                return jsonify({"error": "测试问题不能为空"}), 400
            return jsonify(self.dialogue_manager.rag_test(question, merchant_id=merchant_id))

        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({"error": "页面或接口不存在"}), 404

        @self.app.errorhandler(500)
        def internal_error(error):
            return jsonify({"error": "服务器内部错误"}), 500

    def run(self, debug: bool = True) -> None:
        print(f"AI 智能客服系统启动：http://127.0.0.1:{self.port}")
        self.app.run(host="0.0.0.0", port=self.port, debug=debug, threaded=True)

    def _sse(self, event: str, data: Dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
