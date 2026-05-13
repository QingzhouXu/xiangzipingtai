document.addEventListener('DOMContentLoaded', () => {
    // 用户端脚本：负责心跳展示、SSE 流式聊天、Markdown 渲染和演示重置。
    const merchantId = document.body.dataset.merchantId;
    const chatContainer = document.getElementById('chat-container');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const resetButton = document.getElementById('reset-demo');

    startHeartbeat();

    if (!merchantId || !chatContainer) {
        return;
    }

    document.querySelectorAll('.quick-btn').forEach((button) => {
        button.addEventListener('click', () => sendMessage(button.dataset.message || button.textContent));
    });

    sendButton.addEventListener('click', () => sendMessage(messageInput.value));
    messageInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage(messageInput.value);
        }
    });

    resetButton.addEventListener('click', async () => {
        await fetch('/api/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ merchant_id: merchantId })
        });
        chatContainer.innerHTML = '';
        addMessage('演示已重置。您好，我是当前商家的 AI 客服，可以重新开始提问。', false);
    });

    async function sendMessage(message) {
        // 使用 fetch 读取 text/event-stream，断流时保留已经生成的内容。
        const text = (message || '').trim();
        if (!text) return;

        addMessage(text, true);
        messageInput.value = '';

        const botMessage = addMessage('AI 思考中...', false, true);
        const textNode = botMessage.querySelector('.message-text');
        let fullText = '';

        try {
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, merchant_id: merchantId })
            });

            if (!response.ok || !response.body) {
                throw new Error('流式接口不可用');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const events = buffer.split('\n\n');
                buffer = events.pop() || '';
                for (const eventText of events) {
                    const parsed = parseSse(eventText);
                    if (parsed.event === 'message') {
                        fullText += parsed.data.content || '';
                        renderMarkdown(textNode, fullText);
                    }
                    if (parsed.event === 'error') {
                        fullText += `\n\n${parsed.data.message || '流式输出中断'}`;
                        renderMarkdown(textNode, fullText);
                    }
                }
                scrollToBottom();
            }
        } catch (error) {
            const fallback = fullText || 'SSE 连接中断，当前对话已保留，请稍后重试。';
            renderMarkdown(textNode, fallback);
            console.error(error);
        }
    }

    function addMessage(message, isUser, streaming = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = `avatar ${isUser ? 'user-avatar' : 'bot-avatar'}`;
        avatarDiv.textContent = isUser ? 'U' : 'AI';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        const textDiv = document.createElement('div');
        textDiv.className = `message-text markdown-body ${streaming ? 'thinking' : ''}`;
        renderMarkdown(textDiv, message);

        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

        contentDiv.appendChild(textDiv);
        contentDiv.appendChild(timeDiv);
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatContainer.appendChild(messageDiv);
        scrollToBottom();
        return messageDiv;
    }

    function renderMarkdown(element, markdown) {
        // marked.js 为本地静态文件，比赛现场无外网也能渲染基础 Markdown。
        element.classList.remove('thinking');
        if (window.marked) {
            element.innerHTML = marked.parse(markdown || '');
        } else {
            element.textContent = markdown || '';
        }
    }

    function parseSse(eventText) {
        const lines = eventText.split('\n');
        const event = (lines.find((line) => line.startsWith('event:')) || 'event: message').replace('event:', '').trim();
        const dataLine = (lines.find((line) => line.startsWith('data:')) || 'data: {}').replace('data:', '').trim();
        try {
            return { event, data: JSON.parse(dataLine) };
        } catch {
            return { event, data: {} };
        }
    }

    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
});

function startHeartbeat() {
    // 每 5 秒请求开发板状态，成功时显示延迟和当前 Ollama 模型。
    const statusEl = document.getElementById('board-status');
    if (!statusEl) return;

    async function refresh() {
        try {
            const response = await fetch('/api/heartbeat');
            const data = await response.json();
            if (data.status === 'success') {
                statusEl.className = 'board-status online';
                statusEl.textContent = `🟢 开发板已连接（${data.latency}ms） · ${data.model}`;
            } else {
                statusEl.className = 'board-status offline';
                statusEl.textContent = '🔴 开发板离线';
            }
        } catch {
            statusEl.className = 'board-status offline';
            statusEl.textContent = '🔴 开发板离线';
        }
    }

    refresh();
    setInterval(refresh, 5000);
}
