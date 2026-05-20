document.addEventListener('DOMContentLoaded', function () {
    var chatMessages = document.getElementById('chat-messages');
    var messageInput = document.getElementById('message-input');
    var sendBtn = document.getElementById('send-btn');
    var chatForm = document.getElementById('chat-form');
    var backendBadge = document.getElementById('backend-badge');
    var backendSwitchBtn = document.getElementById('backend-switch-btn');
    var backendDropdown = document.getElementById('backend-dropdown');

    var officialAvatarSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';
    var userAvatarSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';

    startHeartbeat();

    // ── Backend switch dropdown ──
    if (backendSwitchBtn && backendDropdown) {
        backendSwitchBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            backendDropdown.classList.toggle('open');
        });

        document.addEventListener('click', function () {
            backendDropdown.classList.remove('open');
        });

        backendDropdown.addEventListener('click', function (e) {
            var option = e.target.closest('.backend-option');
            if (!option) return;
            var newBackend = option.dataset.backend;

            backendDropdown.querySelectorAll('.backend-option').forEach(function (opt) { opt.classList.remove('active'); });
            option.classList.add('active');

            backendBadge.textContent = '切换中...';
            backendDropdown.classList.remove('open');

            fetch('/api/llm/switch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ backend: newBackend })
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.status === 'success') {
                        updateBackendBadge(newBackend);
                    } else {
                        backendBadge.textContent = '切换失败';
                    }
                })
                .catch(function () {
                    backendBadge.textContent = '切换失败';
                })
                .finally(function () {
                    refreshHeartbeat();
                });
        });
    }

    initEventListeners();
    loadMyMessages();

    function initEventListeners() {
        if (chatForm) {
            chatForm.addEventListener('submit', sendMessage);
        }
        if (sendBtn) {
            sendBtn.addEventListener('click', sendMessage);
        }
        if (messageInput) {
            messageInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        }
    }

    function loadMyMessages() {
        fetch('/api/official-support/my-messages')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.messages && data.messages.length > 0) {
                    data.messages.forEach(function (msg) {
                        var type = msg.type === 'admin_reply' ? 'official' : 'user';
                        addMessage(msg.message, type, msg.timestamp);
                    });
                } else {
                    addWelcomeMessage();
                }
            })
            .catch(function () {
                addWelcomeMessage();
            });
    }

    function addWelcomeMessage() {
        if (chatMessages && chatMessages.children.length === 0) {
            var welcome = document.createElement('div');
            welcome.className = 'message official';
            welcome.innerHTML = '<div class="message-avatar">' + officialAvatarSvg + '</div><div class="message-content"><div>您好！欢迎联系官方客服，请描述您的问题。</div></div>';
            chatMessages.appendChild(welcome);
        }
    }

    function sendMessage(e) {
        if (e) e.preventDefault();
        var message = messageInput ? messageInput.value.trim() : '';
        if (!message) return;

        addMessage(message, 'user');
        if (messageInput) messageInput.value = '';
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.textContent = '发送中...';
        }

        // Show typing indicator
        var typingEl = addTypingIndicator();
        var botMessage = null;
        var textNode = null;
        var fullText = '';

        fetch('/api/official-support/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        })
            .then(function (response) {
                if (!response.ok || !response.body) throw new Error('Stream unavailable');
                var reader = response.body.getReader();
                var decoder = new TextDecoder('utf-8');
                var buffer = '';

                function pump() {
                    return reader.read().then(function (result) {
                        if (result.done) {
                            finishStream();
                            return;
                        }
                        buffer += decoder.decode(result.value, { stream: true });
                        var events = buffer.split('\n\n');
                        buffer = events.pop() || '';
                        events.forEach(function (eventText) {
                            var parsed = parseSseEvent(eventText);
                            if (parsed.event === 'message') {
                                if (!botMessage) {
                                    hideTypingIndicator(typingEl);
                                    botMessage = addMessage('', 'official');
                                    textNode = botMessage.querySelector('.message-content');
                                    textNode.classList.add('streaming');
                                }
                                fullText += parsed.data.content || '';
                                if (textNode) {
                                    textNode.innerHTML = '<div>' + escapeHtml(fullText).replace(/\n/g, '<br>') + '<div class="message-time">' + new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) + '</div></div>';
                                    textNode.classList.remove('chunk-fade');
                                    void textNode.offsetWidth;
                                    textNode.classList.add('chunk-fade');
                                }
                            }
                            if (parsed.event === 'error') {
                                if (!botMessage) {
                                    hideTypingIndicator(typingEl);
                                    botMessage = addMessage('', 'official');
                                    textNode = botMessage.querySelector('.message-content');
                                }
                                fullText += '\n\n' + (parsed.data.message || '输出中断');
                                if (textNode) {
                                    textNode.innerHTML = '<div>' + escapeHtml(fullText).replace(/\n/g, '<br>') + '<div class="message-time">' + new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) + '</div></div>';
                                }
                            }
                            if (parsed.event === 'done') {
                                finishStream();
                                return;
                            }
                        });
                        scrollToBottom();
                        return pump();
                    });
                }
                return pump();

                function finishStream() {
                    if (textNode) textNode.classList.remove('streaming', 'chunk-fade');
                    if (!fullText && !botMessage) {
                        hideTypingIndicator(typingEl);
                        botMessage = addMessage(generateOfficialResponse(message), 'official');
                    }
                    if (sendBtn) {
                        sendBtn.disabled = false;
                        sendBtn.textContent = '发送';
                    }
                }
            })
            .catch(function () {
                hideTypingIndicator(typingEl);
                if (sendBtn) {
                    sendBtn.disabled = false;
                    sendBtn.textContent = '发送';
                }
                if (!fullText) {
                    var fallback = generateOfficialResponse(message);
                    addMessage(fallback, 'official');
                }
            });
    }

    function parseSseEvent(eventText) {
        var lines = eventText.split('\n');
        var event = 'message';
        var data = {};
        lines.forEach(function (line) {
            if (line.startsWith('event:')) event = line.replace('event:', '').trim();
            if (line.startsWith('data:')) {
                try { data = JSON.parse(line.replace('data:', '').trim()); } catch (e) {}
            }
        });
        return { event: event, data: data };
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function addTypingIndicator() {
        if (!chatMessages) return null;
        var el = document.createElement('div');
        el.className = 'message official';
        el.innerHTML = '<div class="message-avatar">' + officialAvatarSvg + '</div><div class="message-content"><div class="typing-indicator"><span class="shining-text">AI is Thinking...</span></div></div>';
        chatMessages.appendChild(el);
        scrollToBottom();
        return el;
    }

    function hideTypingIndicator(el) {
        if (el && el.parentNode) el.remove();
    }

    function addMessage(content, type, timestamp) {
        if (!chatMessages) return;
        var messageDiv = document.createElement('div');
        messageDiv.className = 'message ' + type;

        var avatar = type === 'user' ? userAvatarSvg : officialAvatarSvg;
        var time = timestamp
            ? new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
            : new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

        messageDiv.innerHTML = '<div class="message-avatar">' + avatar + '</div><div class="message-content">' + content + '<div class="message-time">' + time + '</div></div>';
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        return messageDiv;
    }

    function generateOfficialResponse(userMessage) {
        var message = userMessage.toLowerCase();
        if (message.includes('注册') || message.includes('账号')) {
            return '您可以在首页点击"登录/注册"按钮创建账号。注册后即可收藏店铺和使用AI客服服务。如果遇到问题，可以尝试使用演示账号：user/123456';
        }
        if (message.includes('商户') || message.includes('入驻') || message.includes('申请')) {
            return '商户入驻请访问首页，点击"商户入驻申请"按钮。填写相关信息并提交申请，平台管理员会在1-3个工作日内审核。审核通过后即可使用商家管理后台。';
        }
        if (message.includes('ai') || message.includes('客服') || message.includes('机器人')) {
            return '我们的AI客服基于先进的自然语言处理技术，可以理解用户意图并提供准确的回复。商家可以在后台自定义AI形象和知识库，提升服务质量。';
        }
        if (message.includes('收藏') || message.includes('喜欢')) {
            return '您可以在店铺卡片上点击"收藏"按钮来收藏喜欢的店铺。收藏后可以在"我的收藏"页面快速访问。';
        }
        if (message.includes('搜索') || message.includes('找')) {
            return '您可以使用首页的搜索功能查找店铺，支持按店铺名称、类别或关键词搜索。';
        }
        if (message.includes('问题') || message.includes('帮助') || message.includes('怎么用')) {
            return '平台主要功能包括：\n1. 浏览和搜索商家店铺\n2. 与AI客服实时对话\n3. 收藏喜欢的店铺\n4. 商户入驻和管理\n5. 官方客服支持\n\n您有具体想了解的功能吗？';
        }
        if (message.includes('费用') || message.includes('价格') || message.includes('收费')) {
            return '目前平台处于测试阶段，所有功能均免费使用。后续可能会推出付费增值服务，但基础功能将保持免费。';
        }
        if (message.includes('安全') || message.includes('隐私')) {
            return '我们非常重视用户隐私和数据安全。所有对话数据都经过加密处理，不会泄露给第三方。';
        }
        if (message.includes('投诉') || message.includes('举报')) {
            return '如果您遇到问题需要投诉，请提供详细的信息：\n1. 相关店铺名称\n2. 问题描述\n3. 发生时间\n\n我们会尽快处理并回复您。';
        }
        var defaultResponses = [
            '感谢您的咨询！我会尽力帮助您解决问题。请详细描述您的需求。',
            '我理解您的问题。让我为您提供一些有用的信息和建议。',
            '很高兴为您服务！如果您有其他问题，随时可以询问。',
            '您的反馈对我们很重要。请告诉我更多详细信息，以便更好地帮助您。'
        ];
        return defaultResponses[Math.floor(Math.random() * defaultResponses.length)];
    }

    function scrollToBottom() {
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    if (messageInput) {
        messageInput.focus();
    }

    // ── 3D tilt effect for sidebar cards and chat widget ──
    (function() {
        function applyTilt(elements, strength) {
            strength = strength || 6;
            elements.forEach(function(card) {
                var rafId = null;
                var targetRx = 0, targetRy = 0;
                var currentRx = 0, currentRy = 0;

                card.addEventListener('mousemove', function(e) {
                    var rect = card.getBoundingClientRect();
                    targetRx = ((e.clientY - rect.top) / rect.height - 0.5) * -strength;
                    targetRy = ((e.clientX - rect.left) / rect.width - 0.5) * strength;
                    if (!rafId) {
                        rafId = requestAnimationFrame(update);
                    }
                });

                card.addEventListener('mouseleave', function() {
                    targetRx = 0;
                    targetRy = 0;
                    if (!rafId) {
                        rafId = requestAnimationFrame(update);
                    }
                });

                function update() {
                    currentRx += (targetRx - currentRx) * 0.12;
                    currentRy += (targetRy - currentRy) * 0.12;

                    var settled = Math.abs(targetRx - currentRx) < 0.01 && Math.abs(targetRy - currentRy) < 0.01;

                    if (settled && targetRx === 0 && targetRy === 0) {
                        card.style.transform = '';
                        rafId = null;
                    } else if (settled) {
                        card.style.transform = 'perspective(1200px) rotateX(' + targetRx.toFixed(2) + 'deg) rotateY(' + targetRy.toFixed(2) + 'deg)';
                        rafId = null;
                    } else {
                        card.style.transform = 'perspective(1200px) rotateX(' + currentRx.toFixed(2) + 'deg) rotateY(' + currentRy.toFixed(2) + 'deg)';
                        rafId = requestAnimationFrame(update);
                    }
                }
            });
        }

        applyTilt(document.querySelectorAll('.support-info-card, .support-quick-links'), 12);
        applyTilt(document.querySelectorAll('.support-chat'), 6);
    })();

    // ── Heartbeat ──
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
            dropdown.querySelectorAll('.backend-option').forEach(function (opt) {
                opt.classList.toggle('active', opt.dataset.backend === backend);
            });
        }
    }

    function refreshHeartbeat() {
        var statusEl = document.getElementById('board-status');
        var statusDot = document.getElementById('status-dot');

        fetch('/api/heartbeat')
            .then(function (resp) { return resp.json(); })
            .then(function (data) {
                updateBackendBadge(data.backend || 'ollama');

                if (statusEl) {
                    if (data.status === 'success') {
                        statusEl.textContent = '在线服务中（' + data.latency + 'ms）';
                        if (statusDot) statusDot.className = 'chat-status-dot';
                    } else {
                        statusEl.textContent = 'AI 客服离线';
                        if (statusDot) statusDot.className = 'chat-status-dot offline';
                    }
                }
            })
            .catch(function () {
                if (statusEl) statusEl.textContent = 'AI 客服离线';
                if (statusDot) statusDot.className = 'chat-status-dot offline';
            });
    }
});
