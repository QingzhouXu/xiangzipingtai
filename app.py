#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""项目根入口：直接运行 `python app.py` 启动比赛演示系统。"""

import os
import sys


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from dialogue.dialogue_manager import DialogueManager
from ui.web_ui import WebUI


def create_app():
    """创建 Flask app，方便测试和直接运行复用。"""
    dialogue_manager = DialogueManager(use_mock_llm=False)
    return WebUI(dialogue_manager, port=int(os.getenv("PORT", "5000"))).app


if __name__ == "__main__":
    manager = DialogueManager(use_mock_llm=False)
    WebUI(manager, port=int(os.getenv("PORT", "5000"))).run(debug=True)
