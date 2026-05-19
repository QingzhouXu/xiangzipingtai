document.addEventListener('DOMContentLoaded', () => {
    const merchantId = document.body.dataset.merchantId;
    const chatContainer = document.getElementById('chat-container');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const resetButton = document.getElementById('reset-demo');
    const quickReplies = document.getElementById('quick-replies');
    const backendBadge = document.getElementById('backend-badge');
    const backendSwitchBtn = document.getElementById('backend-switch-btn');
    const backendDropdown = document.getElementById('backend-dropdown');

    startHeartbeat();

    // Backend switch dropdown toggle
    if (backendSwitchBtn && backendDropdown) {
        backendSwitchBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            backendDropdown.classList.toggle('open');
        });

        document.addEventListener('click', () => {
            backendDropdown.classList.remove('open');
        });

        backendDropdown.addEventListener('click', async (e) => {
            const option = e.target.closest('.backend-option');
            if (!option) return;
            const newBackend = option.dataset.backend;

            // Update dropdown visual state
            backendDropdown.querySelectorAll('.backend-option').forEach(opt => opt.classList.remove('active'));
            option.classList.add('active');

            // Set badge to loading
            backendBadge.textContent = '切换中...';
            backendDropdown.classList.remove('open');

            try {
                const resp = await fetch('/api/llm/switch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ backend: newBackend })
                });
                const data = await resp.json();
                if (data.status === 'success') {
                    updateBackendBadge(newBackend);
                } else {
                    backendBadge.textContent = '切换失败';
                    console.error('Backend switch failed:', data.error || data);
                }
            } catch (err) {
                backendBadge.textContent = '切换失败';
                console.error('Backend switch error:', err);
            }

            // Refresh heartbeat to reflect new state
            refreshHeartbeat();
        });
    }

    if (!merchantId || !chatContainer) {
        return;
    }

    // Quick reply buttons
    if (quickReplies) {
        quickReplies.addEventListener('click', (e) => {
            const btn = e.target.closest('.quick-reply-btn');
            if (!btn) return;
            const msg = btn.dataset.message || btn.textContent.trim();
            sendMessage(msg);
        });
    }

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
        addWelcomeCard();
    });

    function addWelcomeCard() {
        chatContainer.innerHTML = `
            <div class="chat-welcome">
                <div class="welcome-avatar">🤖</div>
                <h3>您好！欢迎光临</h3>
                <p>我是您的 AI 客服助手，有什么可以帮助您的？</p>
            </div>
        `;
    }

    async function sendMessage(message) {
        const text = (message || '').trim();
        if (!text) return;

        // Remove welcome card if present
        var welcome = chatContainer.querySelector('.chat-welcome');
        if (welcome) welcome.remove();

        addMessage(text, true);
        messageInput.value = '';

        var typingEl = showTypingIndicator();

        var botMessage = addMessage('', false, true);
        var textNode = botMessage.querySelector('.message-text');
        var fullText = '';

        try {
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, merchant_id: merchantId })
            });

            if (response.redirected) {
                window.location.href = response.url;
                return;
            }
            if (!response.ok || !response.body) {
                throw new Error('咨询服务暂时不可用');
            }

            hideTypingIndicator(typingEl);

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
                        fullText += '\n\n' + (parsed.data.message || '输出中断');
                        renderMarkdown(textNode, fullText);
                    }
                }
                scrollToBottom();
            }

            if (!fullText) {
                renderMarkdown(textNode, '收到回复，但内容为空。请再试一次。');
                hideTypingIndicator(typingEl);
            }
        } catch (error) {
            hideTypingIndicator(typingEl);
            const fallback = fullText || '连接中断，当前对话已保留，请稍后重试。';
            renderMarkdown(textNode, fallback);
            console.error(error);
        }
    }

    function showTypingIndicator() {
        var el = document.createElement('div');
        el.className = 'message bot-message typing-message';
        el.innerHTML = '<div class="avatar bot-avatar">AI</div><div class="message-content"><div class="message-text typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div></div>';
        chatContainer.appendChild(el);
        scrollToBottom();
        return el;
    }

    function hideTypingIndicator(el) {
        if (el && el.parentNode) {
            el.remove();
        }
    }

    function addMessage(message, isUser, streaming) {
        var messageDiv = document.createElement('div');
        messageDiv.className = 'message ' + (isUser ? 'user-message' : 'bot-message');

        var avatarDiv = document.createElement('div');
        avatarDiv.className = 'avatar ' + (isUser ? 'user-avatar' : 'bot-avatar');
        avatarDiv.textContent = isUser ? 'U' : 'AI';

        var contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        var textDiv = document.createElement('div');
        textDiv.className = 'message-text markdown-body' + (streaming ? ' thinking' : '');
        if (message) {
            renderMarkdown(textDiv, message);
        }

        var timeDiv = document.createElement('div');
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
        chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' });
    }
});

function startHeartbeat() {
    refreshHeartbeat();
    setInterval(refreshHeartbeat, 5000);
}

function updateBackendBadge(backend) {
    var el = document.getElementById('backend-badge');
    if (!el) return;
    var labels = { dashscope: 'Qwen云端', ollama: '本地模型', mock: '演示模式' };
    el.textContent = labels[backend] || backend;

    var dropdown = document.getElementById('backend-dropdown');
    if (dropdown) {
        dropdown.querySelectorAll('.backend-option').forEach(function(opt) {
            opt.classList.toggle('active', opt.dataset.backend === backend);
        });
    }
}

function refreshHeartbeat() {
    var statusEl = document.getElementById('board-status');
    var statusDot = document.getElementById('status-dot');

    fetch('/api/heartbeat')
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            updateBackendBadge(data.backend || 'ollama');

            if (statusEl) {
                if (data.status === 'success') {
                    statusEl.textContent = 'AI 客服在线（' + data.latency + 'ms）';
                    if (statusDot) statusDot.className = 'status-dot online';
                } else {
                    statusEl.textContent = 'AI 客服离线';
                    if (statusDot) statusDot.className = 'status-dot offline';
                }
            }
        })
        .catch(function() {
            if (statusEl) statusEl.textContent = 'AI 客服离线';
            if (statusDot) statusDot.className = 'status-dot offline';
        });
}
