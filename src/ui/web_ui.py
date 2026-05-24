#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Flask Web 层。
提供客户端、商户端、平台审核、流式咨询和常见问题管理能力。
"""

import base64
import json
import os
import re
import time as _time
import uuid
from functools import wraps
from typing import Dict, Optional
from urllib.request import Request as UrllibRequest, urlopen

from flask import Flask, Response, jsonify, redirect, render_template, request, session, stream_with_context, url_for
from llm.qwen_client import QwenCloudClient
import datetime


class DemoAuthStore:
    """演示级账号与审核数据，使用 JSON 持久化。"""

    def __init__(self, auth_file: str):
        self.auth_file = auth_file
        self.data = self._load()

    def _load(self) -> Dict:
        if os.path.exists(self.auth_file):
            try:
                with open(self.auth_file, "r", encoding="utf-8") as file:
                    return json.load(file)
            except (OSError, json.JSONDecodeError):
                pass
        data = {
            "users": [
                {"id": "u_demo", "username": "user", "password": "123456", "role": "customer", "display_name": "用户昵称_张三"},
                {"id": "m_tea", "username": "tea", "password": "123456", "role": "merchant", "display_name": "星巴克店长", "merchant_id": "tea_shop", "status": "approved"},
                {"id": "m_pending", "username": "pending", "password": "123456", "role": "merchant", "display_name": "待审核商户", "merchant_id": "pending_demo", "status": "pending"},
                {"id": "admin", "username": "admin", "password": "123456", "role": "super_admin", "display_name": "平台管理员"},
            ],
            "applications": [
                {
                    "id": "app_pending_demo",
                    "merchant_id": "pending_demo",
                    "merchant_name": "云朵甜品",
                    "category": "甜品饮品",
                    "contact": "18800001111",
                    "license": "营业执照预览图.png",
                    "status": "pending",
                    "owner_username": "pending",
                }
            ],
        }
        self._save(data)
        return data

    def _save(self, data: Optional[Dict] = None) -> None:
        if data is not None:
            self.data = data
        os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)
        with open(self.auth_file, "w", encoding="utf-8") as file:
            json.dump(self.data, file, ensure_ascii=False, indent=2)

    def login(self, username: str, password: str) -> Optional[Dict]:
        return next((user for user in self.data["users"] if user["username"] == username and user["password"] == password), None)

    def register_customer(self, username: str, password: str) -> Dict:
        if self.find_user(username):
            raise ValueError("用户名已存在")
        user = {"id": uuid.uuid4().hex[:10], "username": username, "password": password, "role": "customer", "display_name": username}
        self.data["users"].append(user)
        self._save()
        return user

    def submit_application(self, username: str, password: str, merchant_name: str, category: str, contact: str, license_name: str, avatar_data: str = "", license_data: str = "") -> Dict:
        if self.find_user(username):
            raise ValueError("用户名已存在")
        merchant_id = f"merchant_{uuid.uuid4().hex[:8]}"
        user = {
            "id": uuid.uuid4().hex[:10],
            "username": username,
            "password": password,
            "role": "merchant",
            "display_name": f"{merchant_name} 管理员",
            "merchant_id": merchant_id,
            "status": "pending",
        }
        application = {
            "id": uuid.uuid4().hex[:10],
            "merchant_id": merchant_id,
            "merchant_name": merchant_name,
            "category": category,
            "contact": contact,
            "license": license_name or "资质证明预览.png",
            "avatar_data": avatar_data,
            "license_data": license_data,
            "status": "pending",
            "owner_username": username,
        }
        self.data["users"].append(user)
        self.data["applications"].append(application)
        self._save()
        return application

    def find_user(self, username: str) -> Optional[Dict]:
        return next((user for user in self.data["users"] if user["username"] == username), None)

    def update_application(self, application_id: str, status: str) -> Optional[Dict]:
        application = next((item for item in self.data["applications"] if item["id"] == application_id), None)
        if not application:
            return None
        application["status"] = status
        user = self.find_user(application["owner_username"])
        if user:
            user["status"] = "approved" if status == "approved" else "rejected"
        self._save()
        return application


class WebUI:
    """Web 应用封装。"""

    def __init__(self, dialogue_manager, port: int = 5000):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_dir = os.path.join(project_root, "src", "ui", "templates")
        static_dir = os.path.join(project_root, "src", "ui", "static")
        auth_file = os.path.join(project_root, "data", "auth_store.json")
        self.app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
        self.app.secret_key = os.getenv("FLASK_SECRET_KEY", "ai-customer-service-demo")
        self.dialogue_manager = dialogue_manager
        self.auth = DemoAuthStore(auth_file)
        self.port = port
        self.register_routes()

    def current_user(self) -> Optional[Dict]:
        username = session.get("username")
        return self.auth.find_user(username) if username else None

    def login_required(self, roles=None):
        roles = roles or []

        def decorator(view):
            @wraps(view)
            def wrapper(*args, **kwargs):
                user = self.current_user()
                if not user:
                    return redirect(url_for("login", next=request.path))
                if roles and user.get("role") not in roles:
                    return redirect(url_for("index"))
                return view(*args, **kwargs)

            return wrapper

        return decorator

    def register_routes(self) -> None:
        @self.app.context_processor
        def inject_globals():
            return {"current_user": self.current_user()}

        @self.app.route("/")
        def index():
            merchants = self._visible_merchants()
            # 计算所有分类及其商家数量
            categories = {}
            for m in merchants:
                cat = m.get("category", "其他")
                categories[cat] = categories.get(cat, 0) + 1
            return render_template("client_home.html", merchants=merchants, categories=categories)

        @self.app.route("/profile")
        @self.login_required(["customer", "merchant", "super_admin"])
        def profile():
            return render_template("profile.html", merchants=self._visible_merchants())

        @self.app.route("/history")
        @self.login_required(["customer", "merchant", "super_admin"])
        def history_page():
            return render_template("history.html", merchants=self._visible_merchants())

        @self.app.route("/api/profile", methods=["PUT"])
        @self.login_required(["customer", "merchant", "super_admin"])
        def update_profile():
            data = request.get_json(silent=True) or {}
            user = self.current_user()
            
            if not user:
                return jsonify({"error": "用户未登录"}), 401
            
            # 更新用户信息
            if data.get("display_name"):
                user["display_name"] = data["display_name"]
            if data.get("phone"):
                user["phone"] = data["phone"]
            if data.get("email"):
                user["email"] = data["email"]
            
            self.auth._save()
            return jsonify({"success": True, "user": user})

        @self.app.route("/api/profile/avatar", methods=["PUT"])
        @self.login_required(["customer", "merchant", "super_admin"])
        def update_avatar():
            data = request.get_json(silent=True) or {}
            user = self.current_user()
            
            if not user:
                return jsonify({"error": "用户未登录"}), 401
            
            avatar_data = data.get("avatar_data", "")
            if avatar_data:
                user["avatar_data"] = avatar_data
                self.auth._save()
                return jsonify({"success": True, "avatar_data": avatar_data})
            
            return jsonify({"error": "头像数据不能为空"}), 400

        @self.app.route("/search")
        def search():
            search_query = request.args.get("q", "").strip()
            merchants = self._visible_merchants()
            
            if search_query:
                # 简单的搜索过滤
                search_lower = search_query.lower()
                merchants = [
                    m for m in merchants 
                    if search_lower in m["name"].lower() 
                    or search_lower in m["category"].lower() 
                    or search_lower in m.get("slogan", "").lower()
                ]
            
            return render_template("search.html", merchants=merchants, search_query=search_query)

        @self.app.route("/categories")
        def categories():
            merchants = self._visible_merchants()
            categories = {}
            
            # 按分类分组
            for merchant in merchants:
                category = merchant.get("category", "其他")
                if category not in categories:
                    categories[category] = []
                categories[category].append(merchant)
            
            return render_template("categories.html", categories=categories)

        @self.app.route("/favorites")
        @self.login_required(["customer", "merchant", "super_admin"])
        def favorites():
            return render_template("favorites.html")

        @self.app.route("/merchant")
        @self.login_required(["merchant", "super_admin"])
        def merchant_portal():
            user = self.current_user()
            if user and user.get("role") == "super_admin":
                return redirect(url_for("platform_admin"))
            if user and user.get("role") == "merchant" and user.get("status") != "approved":
                application = next((item for item in self.auth.data["applications"] if item["owner_username"] == user["username"]), None)
                return render_template("pending.html", application=application)
            return render_template("merchant_portal.html")

        @self.app.route("/official-support")
        def official_support():
            return render_template("official_support.html")

        @self.app.route("/login", methods=["GET", "POST"])
        def login():
            if request.method == "POST":
                username = (request.form.get("username") or "").strip()
                password = (request.form.get("password") or "").strip()
                user = self.auth.login(username, password)
                if user:
                    session["username"] = user["username"]
                    return redirect(request.args.get("next") or url_for("index"))
                return render_template("auth.html", mode="login", error="账号或密码不正确")
            return render_template("auth.html", mode="login")

        @self.app.route("/register", methods=["GET", "POST"])
        def register():
            if request.method == "POST":
                username = (request.form.get("username") or "").strip()
                password = (request.form.get("password") or "").strip()
                if not username or not password:
                    return render_template("auth.html", mode="register", error="请填写账号和密码")
                try:
                    user = self.auth.register_customer(username, password)
                    session["username"] = user["username"]
                    return redirect(url_for("index"))
                except ValueError as exc:
                    return render_template("auth.html", mode="register", error=str(exc))
            return render_template("auth.html", mode="register")

        @self.app.route("/logout")
        def logout():
            session.clear()
            return redirect(url_for("index"))

        @self.app.route("/merchant/apply", methods=["GET", "POST"])
        def merchant_apply():
            if request.method == "POST":
                try:
                    # 处理文件上传
                    avatar_data = request.form.get("avatar_data", "")
                    license_data = request.form.get("license_data", "")
                    
                    application = self.auth.submit_application(
                        username=(request.form.get("username") or "").strip(),
                        password=(request.form.get("password") or "").strip(),
                        merchant_name=(request.form.get("merchant_name") or "").strip(),
                        category=(request.form.get("category") or "").strip(),
                        contact=(request.form.get("contact") or "").strip(),
                        license_name=(request.form.get("license_name") or request.form.get("license_file") or "资质文件"),
                        avatar_data=avatar_data,
                        license_data=license_data
                    )
                    session["username"] = application["owner_username"]
                    return redirect(url_for("admin"))
                except ValueError as exc:
                    return render_template("onboarding.html", error=str(exc))
            return render_template("onboarding.html")

        @self.app.route("/chat")
        @self.login_required(["customer", "merchant", "super_admin"])
        def chat_page():
            merchant_id = request.args.get("merchant", "tea_shop")
            merchant = self.dialogue_manager.knowledge_base.get_merchant(merchant_id)
            knowledge = self.dialogue_manager.knowledge_base.get_knowledge(merchant_id) if merchant else []
            return render_template("client_chat.html", merchant=merchant, merchants=self._visible_merchants(), knowledge=knowledge)

        @self.app.route("/admin")
        @self.login_required(["merchant", "super_admin"])
        def admin():
            user = self.current_user()
            if not user:
                return redirect(url_for("login"))
            if user["role"] == "super_admin":
                return redirect(url_for("platform_admin"))
            if user["role"] == "merchant" and user.get("status") != "approved":
                application = next((item for item in self.auth.data["applications"] if item["owner_username"] == user["username"]), None)
                return render_template("pending.html", application=application)
            merchant = self._current_merchant()
            stats = self._get_merchant_stats(merchant["id"]) if merchant else {}
            return render_template("admin_dashboard.html", merchant=merchant, merchants=self._admin_merchants(), stats=stats)

        @self.app.route("/admin/store")
        @self.login_required(["merchant", "super_admin"])
        def admin_store():
            user = self.current_user()
            if user and user.get("role") == "super_admin":
                return redirect(url_for("platform_admin"))
            return render_template("admin_store.html", merchant=self._current_merchant(), merchants=self._admin_merchants())

        @self.app.route("/admin/persona")
        @self.login_required(["merchant", "super_admin"])
        def admin_persona():
            user = self.current_user()
            if user and user.get("role") == "super_admin":
                return redirect(url_for("platform_admin"))
            return render_template("admin_persona.html", merchant=self._current_merchant(), merchants=self._admin_merchants())

        @self.app.route("/admin/messages")
        @self.login_required(["merchant", "super_admin"])
        def admin_messages():
            user = self.current_user()
            if user and user.get("role") == "super_admin":
                return redirect(url_for("platform_admin"))
            return render_template("admin_messages.html", merchant=self._current_merchant(), merchants=self._admin_merchants())

        @self.app.route("/admin/settings")
        @self.login_required(["merchant", "super_admin"])
        def admin_settings():
            user = self.current_user()
            if user and user.get("role") == "super_admin":
                return redirect(url_for("platform_admin"))
            return render_template("admin_settings.html", merchant=self._current_merchant(), merchants=self._admin_merchants())

        @self.app.route("/platform/admin")
        @self.login_required(["super_admin"])
        def platform_admin():
            return render_template("platform_admin.html", applications=self.auth.data["applications"])

        @self.app.route("/api/platform/applications/<application_id>/<action>", methods=["POST"])
        @self.login_required(["super_admin"])
        def review_application(application_id, action):
            if action not in {"approve", "reject"}:
                return jsonify({"error": "不支持的操作"}), 400
            status = "approved" if action == "approve" else "rejected"
            application = self.auth.update_application(application_id, status)
            if not application:
                return jsonify({"error": "申请不存在"}), 404
            if status == "approved":
                self._ensure_merchant(application)
            return jsonify({"success": True, "application": application})

        @self.app.route("/api/official-support/messages", methods=["GET"])
        @self.login_required(["super_admin"])
        def get_official_messages():
            # 获取所有官方客服消息（仅返回用户消息，管理员回复不混入列表）
            messages = self.auth.data.get("official_messages", [])
            # 兼容旧数据：如果没有顶层 username 字段，从 user_info 中提取
            for msg in messages:
                if not msg.get("username") and msg.get("user_info"):
                    msg["username"] = msg["user_info"].get("username", "访客用户")
            # 仅返回用户消息
            filtered = [m for m in messages if m.get("type") == "user"]
            return jsonify({"messages": filtered})

        @self.app.route("/api/official-support/messages", methods=["POST"])
        @self.login_required(["customer", "merchant", "super_admin"])
        def send_official_message():
            # 发送官方客服消息
            data = request.get_json(silent=True) or {}
            message = (data.get("message") or "").strip()
            user_info = data.get("user_info", {})

            if not message:
                return jsonify({"error": "消息不能为空"}), 400

            # 初始化消息存储
            if "official_messages" not in self.auth.data:
                self.auth.data["official_messages"] = []

            # 获取当前登录用户信息
            current_user = self.current_user()
            username = current_user.get("display_name") or current_user.get("username", "访客用户") if current_user else "访客用户"

            # 添加用户消息
            user_message = {
                "id": str(len(self.auth.data["official_messages"]) + 1),
                "type": "user",
                "message": message,
                "username": username,
                "timestamp": datetime.datetime.now().isoformat(),
                "status": "unread"
            }
            self.auth.data["official_messages"].append(user_message)

            # 生成官方回复
            official_response = {
                "id": str(len(self.auth.data["official_messages"]) + 1),
                "type": "official",
                "message": self._generate_official_response(message),
                "timestamp": datetime.datetime.now().isoformat(),
                "status": "sent"
            }
            self.auth.data["official_messages"].append(official_response)
            
            self.auth._save()
            
            return jsonify({"success": True, "response": official_response["message"]})

        @self.app.route("/api/official-support/stream", methods=["POST"])
        def official_stream():
            """官方客服流式响应，同时保存消息到数据库。"""
            data = request.get_json(silent=True) or {}
            message = (data.get("message") or "").strip()
            if not message:
                return jsonify({"error": "消息不能为空"}), 400

            # 先保存用户消息
            if "official_messages" not in self.auth.data:
                self.auth.data["official_messages"] = []
            current_user = self.current_user()
            username = (current_user.get("display_name") or current_user.get("username", "访客用户")) if current_user else "访客用户"
            user_msg = {
                "id": str(len(self.auth.data["official_messages"]) + 1),
                "type": "user",
                "message": message,
                "username": username,
                "timestamp": datetime.datetime.now().isoformat(),
                "status": "unread"
            }
            self.auth.data["official_messages"].append(user_msg)

            def event_stream():
                full_response = ""
                try:
                    msgs = [
                        {"role": "system", "content": (
                            "你是AI智能客服平台的官方客服助手。你的职责是帮助用户了解和使用平台功能。"
                            "平台功能包括：\n"
                            "1. 浏览和搜索商家店铺（首页）\n"
                            "2. 与商家AI客服实时对话（进入商家详情页）\n"
                            "3. 收藏喜欢的店铺\n"
                            "4. 商户入驻申请（/merchant/apply）\n"
                            "5. 用户注册登录\n\n"
                            "请使用中文，回答要简洁、准确、友好。不要编造不存在的信息。"
                        )},
                        {"role": "user", "content": message}
                    ]
                    for chunk in self.dialogue_manager.llm_client.stream_chat(msgs):
                        full_response += chunk
                        yield self._sse("message", {"content": chunk})
                    yield self._sse("done", {"ok": True})
                except Exception as exc:
                    yield self._sse("error", {"message": f"输出中断：{exc}"})
                    yield self._sse("done", {"ok": False})
                finally:
                    # 保存官方回复（无论成功失败都保存）
                    if full_response:
                        official_resp = {
                            "id": str(len(self.auth.data["official_messages"]) + 1),
                            "type": "official",
                            "message": full_response,
                            "timestamp": datetime.datetime.now().isoformat(),
                            "status": "sent"
                        }
                        self.auth.data["official_messages"].append(official_resp)
                        self.auth._save()
                    elif message:
                        # 流失败时生成关键词回复
                        fallback = self._generate_official_response(message)
                        official_resp = {
                            "id": str(len(self.auth.data["official_messages"]) + 1),
                            "type": "official",
                            "message": fallback,
                            "timestamp": datetime.datetime.now().isoformat(),
                            "status": "sent"
                        }
                        self.auth.data["official_messages"].append(official_resp)
                        self.auth._save()

            return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

        @self.app.route("/api/official-support/messages/<message_id>/reply", methods=["POST"])
        @self.login_required(["super_admin"])
        def reply_official_message(message_id):
            # 管理员回复官方客服消息
            data = request.get_json(silent=True) or {}
            reply_message = (data.get("reply") or data.get("message") or "").strip()
            
            if not reply_message:
                return jsonify({"error": "回复消息不能为空"}), 400
            
            # 查找原消息并标记为已回复
            messages = self.auth.data.get("official_messages", [])
            original_message = None
            for msg in messages:
                if msg["id"] == message_id:
                    msg["status"] = "replied"
                    original_message = msg
                    break
            
            if not original_message:
                return jsonify({"error": "消息不存在"}), 404
            
            # 添加管理员回复
            current_user = self.current_user()
            if not current_user:
                return jsonify({"error": "用户未登录"}), 401
                
            admin_reply = {
                "id": str(len(messages) + 1),
                "type": "admin_reply",
                "message": reply_message,
                "original_message_id": message_id,
                "admin_user": current_user["username"],
                "username": original_message.get("username", ""),
                "timestamp": datetime.datetime.now().isoformat()
            }
            messages.append(admin_reply)
            
            self.auth._save()
            
            return jsonify({"success": True, "reply": admin_reply})

        @self.app.route("/api/official-support/my-messages", methods=["GET"])
        @self.login_required(["customer", "merchant", "super_admin"])
        def get_my_official_messages():
            """客户端获取自己的官方客服对话记录"""
            user = self.current_user()
            username = (user.get("display_name") or user.get("username", "")) if user else ""
            messages = self.auth.data.get("official_messages", [])
            my_messages = [m for m in messages if m.get("username") == username and m.get("type") in ("user", "admin_reply")]
            return jsonify({"messages": my_messages})

        @self.app.route("/api/platform/applications/<application_id>/details", methods=["GET"])
        @self.login_required(["super_admin"])
        def get_application_details(application_id):
            # 获取申请详情
            application = next((item for item in self.auth.data["applications"] if item["id"] == application_id), None)
            if not application:
                return jsonify({"error": "申请不存在"}), 404
            return jsonify({"application": application})

        @self.app.route("/api/platform/merchants", methods=["GET"])
        @self.login_required(["super_admin"])
        def get_platform_merchants():
            # 获取所有商户信息
            merchants = self.dialogue_manager.knowledge_base.list_merchants()
            return jsonify({"merchants": merchants})

        @self.app.route("/api/platform/merchants/<merchant_id>", methods=["PUT"])
        @self.login_required(["super_admin"])
        def update_platform_merchant(merchant_id):
            # 更新商户信息
            data = request.get_json(silent=True) or {}
            kb = self.dialogue_manager.knowledge_base
            merchant = kb.get_merchant(merchant_id)
            
            if not merchant:
                return jsonify({"error": "商户不存在"}), 404
            
            # 更新商户信息
            if data.get("name"):
                merchant["name"] = data["name"]
            if data.get("category"):
                merchant["category"] = data["category"]
            if data.get("slogan"):
                merchant["slogan"] = data["slogan"]
            if data.get("contact"):
                merchant["contact"] = data["contact"]
            if data.get("status"):
                merchant["status"] = data["status"]
            
            kb.save_all(kb.merchants)
            return jsonify({"success": True, "merchant": merchant})

        @self.app.route("/api/platform/merchants/<merchant_id>", methods=["DELETE"])
        @self.login_required(["super_admin"])
        def delete_platform_merchant(merchant_id):
            # 删除商户
            kb = self.dialogue_manager.knowledge_base
            deleted = kb.delete_merchant(merchant_id)
            
            if deleted:
                return jsonify({"success": True, "message": "商户删除成功"})
            else:
                return jsonify({"error": "商户不存在"}), 404

        @self.app.route("/api/platform/statistics", methods=["GET"])
        @self.login_required(["super_admin"])
        def get_platform_statistics():
            # 获取平台统计数据
            users = self.auth.data.get("users", [])
            merchants = self.dialogue_manager.knowledge_base.list_merchants()
            applications = self.auth.data.get("applications", [])
            official_messages = self.auth.data.get("official_messages", [])
            
            # 统计数据
            total_users = len(users)
            total_merchants = len(merchants)
            pending_applications = len([a for a in applications if a.get("status") == "pending"])
            approved_applications = len([a for a in applications if a.get("status") == "approved"])
            rejected_applications = len([a for a in applications if a.get("status") == "rejected"])
            total_messages = len(official_messages)
            unread_messages = len([m for m in official_messages if m.get("status") == "unread"])
            
            # 分类统计
            category_stats = {}
            for merchant in merchants:
                category = merchant.get("category", "其他")
                category_stats[category] = category_stats.get(category, 0) + 1
            
            return jsonify({
                "total_users": total_users,
                "total_merchants": total_merchants,
                "pending_applications": pending_applications,
                "approved_applications": approved_applications,
                "rejected_applications": rejected_applications,
                "total_messages": total_messages,
                "unread_messages": unread_messages,
                "category_stats": category_stats,
                "merchants": merchants
            })

        @self.app.route("/api/platform/settings", methods=["GET"])
        @self.login_required(["super_admin"])
        def get_platform_settings():
            # 获取平台设置
            settings = self.auth.data.get("platform_settings", {
                "platform_name": "AI智能客服平台",
                "platform_description": "提供智能客服服务的平台",
                "enable_registration": True,
                "enable_merchant_application": True,
                "auto_approve_merchant": False
            })
            return jsonify({"settings": settings})

        @self.app.route("/api/platform/settings", methods=["PUT"])
        @self.login_required(["super_admin"])
        def update_platform_settings():
            # 更新平台设置
            data = request.get_json(silent=True) or {}
            
            if "platform_settings" not in self.auth.data:
                self.auth.data["platform_settings"] = {}
            
            # 更新设置
            for key in ["platform_name", "platform_description", "enable_registration", "enable_merchant_application", "auto_approve_merchant"]:
                if key in data:
                    self.auth.data["platform_settings"][key] = data[key]
            
            self.auth._save()
            return jsonify({"success": True, "settings": self.auth.data["platform_settings"]})

        @self.app.route("/api/chat", methods=["POST"])
        @self.login_required(["customer", "merchant", "super_admin"])
        def chat_api():
            data = request.get_json(silent=True) or {}
            message = (data.get("message") or "").strip()
            merchant_id = data.get("merchant_id") or data.get("merchant") or "tea_shop"
            if not message:
                return jsonify({"error": "消息不能为空"}), 400
            try:
                return jsonify({"response": self.dialogue_manager.process_input(message, merchant_id=merchant_id)})
            except Exception as exc:
                return jsonify({"error": f"咨询处理失败：{exc}"}), 500

        @self.app.route("/api/chat/stream", methods=["POST"])
        @self.login_required(["customer", "merchant", "super_admin"])
        def chat_stream():
            data = request.get_json(silent=True) or {}
            message = (data.get("message") or "").strip()
            merchant_id = data.get("merchant_id") or data.get("merchant") or "tea_shop"
            if not message:
                return jsonify({"error": "消息不能为空"}), 400

            def event_stream():
                import concurrent.futures
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            lambda: list(self.dialogue_manager.stream_input(message, merchant_id=merchant_id))
                        )
                        try:
                            chunks = future.result(timeout=180)
                            for chunk in chunks:
                                yield self._sse("message", {"content": chunk})
                            yield self._sse("done", {"ok": True})
                        except concurrent.futures.TimeoutError:
                            yield self._sse("error", {"message": "模型响应超时(180s)，请确认Ollama服务是否正常运行，或切换到演示模式后重试。"})
                            yield self._sse("done", {"ok": False})
                except Exception as exc:
                    yield self._sse("error", {"message": f"输出中断：{exc}"})
                    yield self._sse("done", {"ok": False})

            return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

        @self.app.route("/api/reset", methods=["POST"])
        def reset():
            data = request.get_json(silent=True) or {}
            self.dialogue_manager.reset_dialogue(merchant_id=data.get("merchant_id") or data.get("merchant"))
            return jsonify({"success": True, "message": "对话已清空"})

        @self.app.route("/api/history")
        def history():
            merchant_id = request.args.get("merchant", "tea_shop")
            return jsonify({"history": self.dialogue_manager.get_dialogue_history(merchant_id)})

        @self.app.route("/api/heartbeat")
        def heartbeat():
            return jsonify(self.dialogue_manager.llm_client.heartbeat())

        @self.app.route("/api/llm/switch", methods=["POST"])
        def switch_llm_backend():
            data = request.get_json(silent=True) or {}
            backend = (data.get("backend") or "").strip()
            if backend not in ("ollama", "dashscope", "mock"):
                return jsonify({"error": "不支持的后端，可选: ollama / dashscope / mock"}), 400
            try:
                status = self.dialogue_manager.switch_backend(backend)
                return jsonify(status)
            except Exception as exc:
                return jsonify({"error": f"切换失败：{exc}"}), 500

        @self.app.route("/api/llm/status")
        def llm_status():
            return jsonify(self.dialogue_manager.llm_client.heartbeat())

        @self.app.route("/api/merchants")
        def merchants():
            return jsonify({"merchants": self._visible_merchants()})

        @self.app.route("/api/knowledge")
        @self.login_required(["merchant", "super_admin"])
        def knowledge_list():
            merchant_id = self._merchant_scope(request.args.get("merchant", "tea_shop"))
            kb = self.dialogue_manager.knowledge_base
            merchant = kb.get_merchant(merchant_id)
            return jsonify({"merchant": merchant, "knowledge": kb.get_knowledge(merchant["id"])})

        @self.app.route("/api/knowledge", methods=["POST"])
        @self.login_required(["merchant", "super_admin"])
        def knowledge_add():
            data = request.get_json(silent=True) or {}
            merchant_id = self._merchant_scope(data.get("merchant_id") or "tea_shop")
            question = (data.get("question") or "").strip()
            answer = (data.get("answer") or "").strip()
            if not question or not answer:
                return jsonify({"error": "问题和回答不能为空"}), 400
            item = self.dialogue_manager.knowledge_base.add_knowledge(question, answer, merchant_id=merchant_id)
            return jsonify({"success": True, "item": item})

        @self.app.route("/api/knowledge/<knowledge_id>", methods=["DELETE"])
        @self.login_required(["merchant", "super_admin"])
        def knowledge_delete(knowledge_id):
            merchant_id = self._merchant_scope(request.args.get("merchant", "tea_shop"))
            deleted = self.dialogue_manager.knowledge_base.delete_knowledge(knowledge_id, merchant_id=merchant_id)
            return jsonify({"success": deleted})

        @self.app.route("/api/rag/test", methods=["POST"])
        @self.login_required(["merchant", "super_admin"])
        def rag_test():
            data = request.get_json(silent=True) or {}
            merchant_id = self._merchant_scope(data.get("merchant_id") or "tea_shop")
            question = (data.get("question") or "").strip()
            if not question:
                return jsonify({"error": "测试问题不能为空"}), 400
            return jsonify(self.dialogue_manager.rag_test(question, merchant_id=merchant_id))

        @self.app.route("/api/merchant/store", methods=["POST"])
        @self.login_required(["merchant", "super_admin"])
        def update_merchant_store():
            data = request.get_json(silent=True) or {}
            merchant_id = self._merchant_scope(data.get("merchant_id") or "tea_shop")
            name = (data.get("name") or "").strip()
            slogan = (data.get("slogan") or "").strip()

            if not name or not slogan:
                return jsonify({"error": "店铺名称和简介不能为空"}), 400

            try:
                kb = self.dialogue_manager.knowledge_base
                merchant = kb.get_merchant(merchant_id)
                if not merchant:
                    return jsonify({"error": "商户不存在"}), 404

                # 更新商户信息
                merchant["name"] = name
                merchant["slogan"] = slogan
                if data.get("category"):
                    merchant["category"] = data["category"].strip()
                if data.get("hours"):
                    merchant["hours"] = data["hours"].strip()
                if data.get("address"):
                    merchant["address"] = data["address"].strip()

                # 处理封面图片上传
                cover_image = data.get("cover_image", "")
                if cover_image and cover_image.startswith("data:image"):
                    ext = re.search(r'image/(\w+)', cover_image)
                    ext = ext.group(1) if ext else "png"
                    if ext == "svg+xml":
                        ext = "svg"
                    filename = f"{merchant_id}_cover.{ext}"
                    filepath = os.path.join(self.app.root_path, "static", "img", "shops", filename)
                    img_data = re.sub(r'^data:image/\w+;base64,', '', cover_image)
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(img_data))
                    merchant["cover"] = f"/static/img/shops/{filename}"

                # 处理头像图片上传
                avatar_image = data.get("avatar_image", "")
                if avatar_image and avatar_image.startswith("data:image"):
                    ext = re.search(r'image/(\w+)', avatar_image)
                    ext = ext.group(1) if ext else "png"
                    if ext == "svg+xml":
                        ext = "svg"
                    filename = f"{merchant_id}_avatar.{ext}"
                    filepath = os.path.join(self.app.root_path, "static", "img", "shops", filename)
                    img_data = re.sub(r'^data:image/\w+;base64,', '', avatar_image)
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(img_data))
                    merchant["avatar"] = f"/static/img/shops/{filename}"

                kb.save_all(kb.merchants)

                return jsonify({"success": True, "merchant": merchant})
            except Exception as exc:
                return jsonify({"error": f"更新失败：{exc}"}), 500

        @self.app.route("/api/merchant/import-data", methods=["POST"])
        @self.login_required(["merchant", "super_admin"])
        def import_merchant_data():
            data = request.get_json(silent=True) or {}
            merchant_id = self._merchant_scope(data.get("merchant_id") or "tea_shop")
            raw_text = (data.get("raw_text") or "").strip()

            if not raw_text:
                return jsonify({"error": "资料不能为空"}), 400

            try:
                kb = self.dialogue_manager.knowledge_base
                merchant = kb.get_merchant(merchant_id)
                if not merchant:
                    return jsonify({"error": "商户不存在"}), 404

                # 存储原始导入资料
                merchant["imported_data"] = raw_text

                # 用 LLM 生成知识库条目
                prompt = (
                    f"你是一家店铺的 AI 知识库生成器。根据以下店铺资料，生成 4-8 条常见问题及回答。\n\n"
                    f"店铺名称：{merchant['name']}\n"
                    f"店铺类别：{merchant.get('category', '')}\n"
                    f"店铺简介：{merchant.get('slogan', '')}\n\n"
                    f"店铺详细资料：\n{raw_text}\n\n"
                    "请返回一个 JSON 数组（只返回 JSON，不要其他文字），格式如下：\n"
                    '[\n'
                    '  {"question": "常见问题1", "answer": "对应的回答", "category": "分类名称"},\n'
                    '  {"question": "常见问题2", "answer": "对应的回答", "category": "分类名称"}\n'
                    "]\n"
                    "要求：\n"
                    "1. question 要简洁，像客户会问的自然语言（10-20字）\n"
                    "2. answer 要完整、准确、包含具体信息（如价格、时间等）（30-80字）\n"
                    "3. category 按内容分类，如：招牌推荐、门店信息、配送服务、会员服务、常见问题\n"
                    "4. 生成的内容必须严格基于提供的资料，不要编造"
                )

                generated_items = []
                try:
                    ai_response = self._cloud_llm.generate(prompt)
                    import re as _re
                    json_match = _re.search(r'\[[\s\S]*\]', ai_response)
                    if json_match:
                        items = json.loads(json_match.group())
                        if isinstance(items, list):
                            for item in items:
                                if item.get("question") and item.get("answer"):
                                    q = item["question"].strip()
                                    a = item["answer"].strip()
                                    cat = item.get("category", "常见问题").strip()
                                    entry = kb.add_knowledge(q, a, merchant_id=merchant_id, category=cat)
                                    generated_items.append(entry)

                    # 限制最多 8 条
                    generated_items = generated_items[:8]

                except Exception:
                    pass

                # 保存导入的原始资料（知识条目已由 add_knowledge 自动保存）
                if not generated_items:
                    kb.save_all(kb.merchants)

                return jsonify({
                    "success": True,
                    "count": len(generated_items),
                    "items": generated_items
                })
            except Exception as exc:
                return jsonify({"error": f"导入失败：{exc}"}), 500

        @self.app.route("/api/merchant/visit", methods=["POST"])
        @self.login_required()
        def track_merchant_visit():
            data = request.get_json(silent=True) or {}
            merchant_id = data.get("merchant_id", "")
            if not merchant_id:
                return jsonify({"error": "merchant_id required"}), 400
            stats = self._ensure_merchant_stats(merchant_id)
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            stats["visits"][today] = stats["visits"].get(today, 0) + 1
            self.auth._save()
            return jsonify({"success": True})

        @self.app.route("/api/merchant/consult", methods=["POST"])
        @self.login_required()
        def track_merchant_consult():
            data = request.get_json(silent=True) or {}
            merchant_id = data.get("merchant_id", "")
            if not merchant_id:
                return jsonify({"error": "merchant_id required"}), 400
            stats = self._ensure_merchant_stats(merchant_id)
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            stats["consultations"][today] = stats["consultations"].get(today, 0) + 1
            self.auth._save()
            return jsonify({"success": True})

        @self.app.route("/api/merchant/messages", methods=["GET"])
        @self.login_required(["merchant", "super_admin"])
        def get_merchant_messages():
            merchant_id = self._merchant_scope(request.args.get("merchant_id") or "tea_shop")
            filter_type = request.args.get("filter", "all")
            search = request.args.get("search", "").strip()
            
            try:
                # 从 DialogueManager 会话中获取真实对话记录
                session_key = self.dialogue_manager._session_key(merchant_id)
                session_messages = self.dialogue_manager.sessions.get(session_key, [])
                messages = []
                for i, msg in enumerate(session_messages):
                    content = msg.get("content", "")
                    messages.append({
                        "id": i + 1,
                        "visitor": "用户",
                        "content": content[:100] + ("..." if len(content) > 100 else ""),
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "status": "read",
                        "merchant_id": merchant_id
                    })
                
                # 应用筛选
                if filter_type == "unread":
                    messages = [msg for msg in messages if msg["status"] == "unread"]
                
                # 应用搜索
                if search:
                    messages = [msg for msg in messages if search.lower() in msg["visitor"].lower() or search.lower() in msg["content"].lower()]
                
                return jsonify({"success": True, "messages": messages})
            except Exception as exc:
                return jsonify({"error": f"获取消息失败：{exc}"}), 500

        @self.app.route("/api/merchant/messages/<int:message_id>/read", methods=["POST"])
        @self.login_required(["merchant", "super_admin"])
        def mark_message_read(message_id):
            try:
                # 这里应该更新数据库中的消息状态
                # 目前返回成功状态
                return jsonify({"success": True, "message": "已标记为已读"})
            except Exception as exc:
                return jsonify({"error": f"标记失败：{exc}"}), 500

        @self.app.route("/api/merchant/comments", methods=["GET"])
        def get_merchant_comments():
            merchant_id = request.args.get("merchant_id", "tea_shop")
            comments = self.auth.data.get("comments", {}).get(merchant_id, [])
            return jsonify({"comments": comments})

        @self.app.route("/api/merchant/comments", methods=["POST"])
        @self.login_required(["customer", "merchant", "super_admin"])
        def add_merchant_comment():
            data = request.get_json(silent=True) or {}
            merchant_id = data.get("merchant_id", "tea_shop")
            content = (data.get("content") or "").strip()
            rating = data.get("rating", 5)

            if not content:
                return jsonify({"error": "评论内容不能为空"}), 400

            user = self.current_user()
            comment = {
                "id": uuid.uuid4().hex[:10],
                "merchant_id": merchant_id,
                "username": user["username"] if user else "匿名用户",
                "display_name": user.get("display_name", user["username"]) if user else "匿名用户",
                "content": content[:500],
                "rating": min(5, max(1, int(rating))),
                "timestamp": datetime.datetime.now().isoformat(),
            }

            self.auth.data.setdefault("comments", {}).setdefault(merchant_id, []).append(comment)
            self.auth._save()
            return jsonify({"success": True, "comment": comment})

        @self.app.route("/api/merchant/change-password", methods=["POST"])
        @self.login_required(["merchant", "super_admin"])
        def change_merchant_password():
            data = request.get_json(silent=True) or {}
            merchant_id = self._merchant_scope(data.get("merchant_id") or "tea_shop")
            current_password = (data.get("current_password") or "").strip()
            new_password = (data.get("new_password") or "").strip()
            
            if not current_password or not new_password:
                return jsonify({"error": "请填写当前密码和新密码"}), 400
            
            if len(new_password) < 6:
                return jsonify({"error": "新密码长度至少6位"}), 400
            
            try:
                user = self.current_user()
                if not user or user.get("password") != current_password:
                    return jsonify({"error": "当前密码不正确"}), 400
                
                # 更新密码（实际应用中应该加密存储）
                user["password"] = new_password
                self.auth._save()
                
                return jsonify({"success": True, "message": "密码修改成功"})
            except Exception as exc:
                return jsonify({"error": f"密码修改失败：{exc}"}), 500

        @self.app.route("/api/merchant/change-phone", methods=["POST"])
        @self.login_required(["merchant", "super_admin"])
        def change_merchant_phone():
            data = request.get_json(silent=True) or {}
            merchant_id = self._merchant_scope(data.get("merchant_id") or "tea_shop")
            new_phone = (data.get("new_phone") or "").strip()
            verify_code = (data.get("verify_code") or "").strip()
            
            if not new_phone or not verify_code:
                return jsonify({"error": "请填写手机号和验证码"}), 400
            
            if not re.match(r"^1[3-9]\d{9}$", new_phone):
                return jsonify({"error": "手机号格式不正确"}), 400
            
            try:
                # 这里应该验证验证码的有效性
                # 目前假设验证码为"123456"
                if verify_code != "123456":
                    return jsonify({"error": "验证码不正确"}), 400
                
                # 更新用户手机号
                user = self.current_user()
                if user:
                    user["phone"] = new_phone
                    self.auth._save()
                
                return jsonify({"success": True, "message": "手机号更换成功"})
            except Exception as exc:
                return jsonify({"error": f"手机号更换失败：{exc}"}), 500

        @self.app.route("/api/merchant/persona", methods=["POST"])
        @self.login_required(["merchant", "super_admin"])
        def save_merchant_persona():
            data = request.get_json(silent=True) or {}
            merchant_id = self._merchant_scope(data.get("merchant_id") or "tea_shop")
            persona = data.get("persona", {})
            
            if not persona.get("name") or not persona.get("description"):
                return jsonify({"error": "AI形象信息不完整"}), 400
            
            try:
                kb = self.dialogue_manager.knowledge_base
                merchant = kb.get_merchant(merchant_id)
                if not merchant:
                    return jsonify({"error": "商户不存在"}), 404
                
                # 保存AI形象信息
                merchant["persona"] = persona
                kb.save_all(kb.merchants)
                
                return jsonify({"success": True, "persona": persona, "message": "AI形象保存成功"})
            except Exception as exc:
                return jsonify({"error": f"保存失败：{exc}"}), 500

        @self.app.route("/api/merchant/persona", methods=["GET"])
        @self.login_required(["merchant", "super_admin"])
        def get_merchant_persona():
            merchant_id = self._merchant_scope(request.args.get("merchant", "tea_shop"))
            kb = self.dialogue_manager.knowledge_base
            merchant = kb.get_merchant(merchant_id)
            persona = merchant.get("persona")
            return jsonify({"persona": persona})

        @self.app.route("/api/merchant/persona/generate-image", methods=["POST"])
        @self.login_required(["merchant", "super_admin"])
        def generate_merchant_persona_image():
            data = request.get_json(silent=True) or {}
            merchant_id = self._merchant_scope(data.get("merchant_id") or "tea_shop")
            kb = self.dialogue_manager.knowledge_base
            merchant = kb.get_merchant(merchant_id)
            if not merchant:
                return jsonify({"error": "商户不存在"}), 404

            # 尝试用 DashScope 通义万相生成图片
            api_key = os.getenv("DASHSCOPE_API_KEY", "")
            if api_key:
                try:
                    prompt = (
                        f"一个可爱的{merchant.get('category', '')}店铺AI客服角色头像，"
                        f"店铺名称：{merchant['name']}，{merchant.get('slogan', '')}"
                        f"卡通风格，温暖亲切，商业插画，干净背景，高清晰度"
                    )

                    # 提交任务
                    body = json.dumps({
                        "model": "wanx-v1",
                        "input": {"prompt": prompt},
                        "parameters": {"size": "512x512", "n": 1},
                    }).encode("utf-8")
                    task_req = UrllibRequest(
                        "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
                        data=body,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    with urlopen(task_req, timeout=30) as resp:
                        task_data = json.loads(resp.read())
                    task_id = task_data.get("output", {}).get("task_id", "")
                    if not task_id:
                        return jsonify({"error": "图片生成任务提交失败"}), 500

                    # 轮询结果（最多等待 60 秒）
                    for _ in range(30):
                        _time.sleep(2)
                        poll_req = UrllibRequest(
                            f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                            headers={"Authorization": f"Bearer {api_key}"},
                        )
                        with urlopen(poll_req, timeout=10) as resp:
                            poll_data = json.loads(resp.read())
                        status = poll_data.get("output", {}).get("task_status", "")
                        if status == "SUCCEEDED":
                            results = poll_data.get("output", {}).get("results", [])
                            if results:
                                image_url = results[0].get("url", "")
                                if image_url:
                                    # 下载图片并保存到本地
                                    with urlopen(image_url, timeout=15) as img_resp:
                                        img_data = img_resp.read()
                                    ext = "png"
                                    filename = f"{merchant_id}_persona.{ext}"
                                    filepath = os.path.join(self.app.root_path, "static", "img", "shops", filename)
                                    with open(filepath, "wb") as f:
                                        f.write(img_data)
                                    local_url = f"/static/img/shops/{filename}"
                                    return jsonify({"success": True, "image_url": local_url})
                            break
                        elif status in ("FAILED", "STOPPED"):
                            break

                    return jsonify({"error": "图片生成超时或失败，请稍后重试或手动上传"}), 500
                except Exception as exc:
                    return jsonify({"error": f"图片生成失败：{exc}"}), 500
            else:
                return jsonify({"error": "未配置 AI 图片生成服务，请手动上传图片"}), 400

        @self.app.route("/api/merchant/persona/generate", methods=["POST"])
        @self.login_required(["merchant", "super_admin"])
        def generate_merchant_persona():
            data = request.get_json(silent=True) or {}
            merchant_id = self._merchant_scope(data.get("merchant_id") or "tea_shop")
            kb = self.dialogue_manager.knowledge_base
            merchant = kb.get_merchant(merchant_id)
            if not merchant:
                return jsonify({"error": "商户不存在"}), 404

            try:
                prompt_parts = [
                    "你是一位品牌形象设计师。请为以下店铺设计一个 AI 客服角色。\n",
                    f"店铺名称：{merchant['name']}\n",
                    f"店铺类别：{merchant.get('category', '')}\n",
                    f"店铺简介：{merchant.get('slogan', '')}\n",
                ]
                imported = merchant.get("imported_data", "")
                if imported:
                    prompt_parts.append(f"店铺详细资料：\n{imported[:500]}\n")
                prompt_parts.append(
                    "请返回一个 JSON 对象（只返回 JSON，不要其他文字），包含以下字段：\n"
                    '"name": AI 角色的名字（2-4个字，要有亲和力和品牌感，不要带引号）,\n'
                    '"description": AI 角色的性格描述（30-60字，包含说话风格和服务态度）,\n'
                    '"avatar": 一个 emoji 表情代表这个角色\n'
                    '例如：{"name":"咖啡师小星","description":"亲切专业的咖啡顾问，熟悉每款饮品的风味特点，善于根据顾客口味推荐。","avatar":"☕"}'
                )
                prompt = "".join(prompt_parts)
                ai_response = self._cloud_llm.generate(prompt)

                # Try to extract JSON from AI response
                import re as _re
                json_match = _re.search(r'\{[^{}]*"name"[^{}]*"description"[^{}]*"avatar"[^{}]*\}', ai_response, _re.DOTALL)
                if json_match:
                    persona = json.loads(json_match.group())
                else:
                    # Fallback: template-based generation
                    raise ValueError("AI did not return valid JSON")

                return jsonify({"success": True, "persona": persona})
            except Exception:
                # Fallback to template-based generation
                persona = self._generate_persona_fallback(merchant)
                return jsonify({"success": True, "persona": persona, "fallback": True})

        @self.app.route("/api/merchant/delete-account", methods=["POST"])
        @self.login_required(["merchant", "super_admin"])
        def delete_merchant_account():
            data = request.get_json(silent=True) or {}
            merchant_id = self._merchant_scope(data.get("merchant_id") or "tea_shop")
            
            try:
                user = self.current_user()
                if not user:
                    return jsonify({"error": "用户不存在"}), 404
                
                # 删除商户数据
                kb = self.dialogue_manager.knowledge_base
                if merchant_id in kb.merchants:
                    del kb.merchants[merchant_id]
                    kb.save_all(kb.merchants)
                
                # 删除用户账号
                self.auth.data["users"] = [u for u in self.auth.data["users"] if u["id"] != user["id"]]
                self.auth._save()
                
                return jsonify({"success": True, "message": "商铺注销成功"})
            except Exception as exc:
                return jsonify({"error": f"注销失败：{exc}"}), 500

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

    def _generate_official_response(self, user_message: str) -> str:
        """生成官方客服回复：优先使用 LLM，失败时回退到关键词匹配。"""
        try:
            messages = [
                {"role": "system", "content": (
                    "你是AI智能客服平台的官方客服助手。你的职责是帮助用户了解和使用平台功能。"
                    "平台功能包括：\n"
                    "1. 浏览和搜索商家店铺（首页）\n"
                    "2. 与商家AI客服实时对话（进入商家详情页）\n"
                    "3. 收藏喜欢的店铺\n"
                    "4. 商户入驻申请（/merchant/apply）\n"
                    "5. 用户注册登录\n\n"
                    "请使用中文，回答要简洁、准确、友好。不要编造不存在的信息。"
                )},
                {"role": "user", "content": user_message}
            ]
            response = self.dialogue_manager.llm_client.chat(messages)
            if response and not response.startswith("开发板模型") and not response.startswith("云端模型"):
                return response
        except Exception:
            pass

        # ── LLM 不可用时的关键词兜底 ──
        message = user_message.lower()

        if '注册' in message or '账号' in message:
            return '您可以在首页点击"登录/注册"按钮创建账号。注册后即可收藏店铺和使用AI客服服务。如果遇到问题，可以尝试使用演示账号：user/123456'

        if '商户' in message or '入驻' in message or '申请' in message:
            return '商户入驻请访问首页，点击"商户入驻申请"按钮。填写相关信息并提交申请，平台管理员会在1-3个工作日内审核。审核通过后即可使用商家管理后台。'

        if 'ai' in message or '客服' in message or '机器人' in message:
            return '我们的AI客服基于先进的自然语言处理技术，可以理解用户意图并提供准确的回复。商家可以在后台自定义AI形象和知识库，提升服务质量。'

        if '收藏' in message or '喜欢' in message:
            return '您可以在店铺卡片上点击"收藏"按钮来收藏喜欢的店铺。收藏后可以在"我的收藏"页面快速访问。'

        if '搜索' in message or '找' in message:
            return '您可以使用首页的搜索功能查找店铺，支持按店铺名称、类别或关键词搜索。也可以访问"全部分类"页面按类别浏览。'

        if '问题' in message or '帮助' in message or '怎么用' in message:
            return '平台主要功能包括：\n1. 浏览和搜索商家店铺\n2. 与AI客服实时对话\n3. 收藏喜欢的店铺\n4. 商户入驻和管理\n5. 官方客服支持\n\n您有具体想了解的功能吗？'

        if '费用' in message or '价格' in message or '收费' in message:
            return '目前平台处于测试阶段，所有功能均免费使用。后续可能会推出付费增值服务，但基础功能将保持免费。'

        if '安全' in message or '隐私' in message:
            return '我们非常重视用户隐私和数据安全。所有对话数据都经过加密处理，不会泄露给第三方。'

        if '投诉' in message or '举报' in message:
            return '如果您遇到问题需要投诉，请提供详细的信息：\n1. 相关店铺名称\n2. 问题描述\n3. 发生时间\n\n我们会尽快处理并回复您。'

        default_responses = [
            '感谢您的咨询！我会尽力帮助您解决问题。请详细描述您的需求。',
            '我理解您的问题。让我为您提供一些有用的信息和建议。',
            '很高兴为您服务！如果您有其他问题，随时可以询问。',
            '您的反馈对我们很重要。请告诉我更多详细信息，以便更好地帮助您。'
        ]
        return default_responses[len(user_message) % len(default_responses)]

    def _generate_persona_fallback(self, merchant: Dict) -> Dict:
        """本地模板兜底生成 AI 形象。"""
        name = merchant.get("name", "")
        category = merchant.get("category", "")
        slogan = merchant.get("slogan", "")

        category_personas = {
            "咖啡": {"prefix": "咖啡师", "avatar": "☕", "trait": "亲切专业的咖啡顾问，熟悉每款饮品的风味特点"},
            "茶饮": {"prefix": "茶艺师", "avatar": "🍵", "trait": "温文尔雅的茶文化使者，精通各类茶饮搭配"},
            "甜品": {"prefix": "甜品师", "avatar": "🍰", "trait": "甜美活泼的甜品达人，热爱分享制作故事和口味搭配"},
            "餐饮": {"prefix": "美食家", "avatar": "🍽️", "trait": "热情周到的美食向导，擅长推荐菜品和搭配建议"},
            "生活服务": {"prefix": "小助手", "avatar": "🤖", "trait": "细心体贴的服务顾问，用心解决每一位顾客的需求"},
        }

        info = category_personas.get(category, category_personas["生活服务"])
        persona_name = f"{info['prefix']}小{name[0] if name else '店'}"
        description = f"{info['trait']}，代表{name}品牌形象，{category}专业顾问。{slogan}"

        return {
            "name": persona_name,
            "description": description,
            "avatar": info["avatar"],
        }

    def _visible_merchants(self):
        merchants = self.dialogue_manager.knowledge_base.list_merchants()
        # 用评论平均分覆盖商家评分
        comments_data = self.auth.data.get("comments", {})
        for m in merchants:
            mid = m["id"]
            ratings = [c.get("rating", 0) for c in comments_data.get(mid, []) if c.get("rating")]
            if ratings:
                avg = sum(ratings) / len(ratings)
                m["rating"] = f"{avg:.1f}"
        return merchants

    def _admin_merchants(self):
        user = self.current_user()
        merchants = self.dialogue_manager.knowledge_base.list_merchants()
        if user and user.get("role") == "merchant":
            return [item for item in merchants if item["id"] == user.get("merchant_id")]
        return merchants

    def _current_merchant(self):
        user = self.current_user()
        if user and user.get("role") == "super_admin":
            return None
        merchant_id = request.args.get("merchant")
        if user and user.get("role") == "merchant":
            merchant_id = user.get("merchant_id")
        merchant = self.dialogue_manager.knowledge_base.get_merchant(merchant_id or "tea_shop")
        if merchant:
            # 用评论平均分覆盖评分
            ratings = [c.get("rating", 0) for c in self.auth.data.get("comments", {}).get(merchant["id"], []) if c.get("rating")]
            if ratings:
                merchant["rating"] = f"{sum(ratings) / len(ratings):.1f}"
        return merchant

    def _merchant_scope(self, merchant_id: str) -> str:
        user = self.current_user()
        if user and user.get("role") == "merchant":
            return user.get("merchant_id", merchant_id)
        return merchant_id

    @property
    def _cloud_llm(self):
        """始终返回云端 DashScope 客户端，不受 LLM_BACKEND 环境影响。"""
        if not hasattr(self, "_cloud_llm_cache"):
            self._cloud_llm_cache = QwenCloudClient()
        return self._cloud_llm_cache

    def _ensure_merchant_stats(self, merchant_id: str) -> Dict:
        """Ensure merchant stats exist and return them."""
        if "merchant_stats" not in self.auth.data:
            self.auth.data["merchant_stats"] = {}
        if merchant_id not in self.auth.data["merchant_stats"]:
            self.auth.data["merchant_stats"][merchant_id] = {
                "visits": {},
                "consultations": {},
                "favorites": 0
            }
        return self.auth.data["merchant_stats"][merchant_id]

    def _get_merchant_stats(self, merchant_id: str) -> Dict:
        """Get today's stats for a merchant."""
        stats = self._ensure_merchant_stats(merchant_id)
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_visits = stats["visits"].get(today, 0)
        today_consultations = stats["consultations"].get(today, 0)
        return {
            "today_visits": today_visits,
            "today_consultations": today_consultations,
            "total_favorites": stats.get("favorites", 0)
        }

    def _ensure_merchant(self, application: Dict) -> None:
        kb = self.dialogue_manager.knowledge_base
        merchant_id = application["merchant_id"]
        if merchant_id in kb.merchants:
            return
        kb.merchants[merchant_id] = {
            "id": merchant_id,
            "name": application["merchant_name"],
            "slogan": application["category"],
            "category": application["category"],
            "rating": "4.8",
            "hours": "09:00 - 21:00",
            "address": "待完善",
            "cover": "/static/img/shops/coffee_shop.png",
            "avatar": "/static/img/shops/avatar-store.svg",
            "accent": "#ff5a00",
            "knowledge": [
                {
                    "id": f"{merchant_id}_welcome",
                    "question": "营业时间是什么？",
                    "answer": f"{application['merchant_name']} 的营业时间可以在商家中心完善。",
                    "category": "门店信息",
                }
            ],
        }
        kb.save_all(kb.merchants)
