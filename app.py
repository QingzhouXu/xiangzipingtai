#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""项目根入口：直接运行 `python app.py` 启动比赛演示系统。"""

import os
import sys

from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from dialogue.dialogue_manager import DialogueManager
from ui.web_ui import WebUI


def create_app():
    """创建 Flask app，方便测试和直接运行复用。"""
    backend = os.getenv("LLM_BACKEND", "ollama")
    use_mock = backend == "mock"
    dialogue_manager = DialogueManager(use_mock_llm=use_mock, backend=backend)
    return WebUI(dialogue_manager, port=int(os.getenv("PORT", "5000"))).app


if __name__ == "__main__":
    backend = os.getenv("LLM_BACKEND", "ollama")
    use_mock = backend == "mock"
    manager = DialogueManager(use_mock_llm=use_mock, backend=backend)
    WebUI(manager, port=int(os.getenv("PORT", "5000"))).run(debug=True)
