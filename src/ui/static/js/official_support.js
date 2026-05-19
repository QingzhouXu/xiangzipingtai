document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chat-messages');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    const chatForm = document.getElementById('chat-form');

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
            messageInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        }
    }

    function loadMyMessages() {
        fetch('/api/official-support/my-messages')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.messages && data.messages.length > 0) {
                    data.messages.forEach(function(msg) {
                        var type = msg.type === 'admin_reply' ? 'official' : 'user';
                        addMessage(msg.message, type, msg.timestamp);
                    });
                } else {
                    addWelcomeMessage();
                }
            })
            .catch(function() {
                addWelcomeMessage();
            });
    }

    function addWelcomeMessage() {
        if (chatMessages && chatMessages.children.length === 0) {
            var welcome = document.createElement('div');
            welcome.className = 'message official';
            welcome.innerHTML = '<div class="message-avatar">🎯</div><div class="message-content"><div>您好！欢迎联系官方客服，请描述您的问题。</div></div>';
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

        var userInfoEl = document.querySelector('.support-user-info span');
        var username = userInfoEl ? userInfoEl.textContent : '访客用户';

        fetch('/api/official-support/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, user_info: { username: username } })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success && data.response) {
                addMessage(data.response, 'official');
            }
        })
        .catch(function() {
            var fallback = generateOfficialResponse(message);
            addMessage(fallback, 'official');
        })
        .finally(function() {
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.textContent = '发送';
            }
        });
    }

    function addMessage(content, type, timestamp) {
        if (!chatMessages) return;
        var messageDiv = document.createElement('div');
        messageDiv.className = 'message ' + type;

        var avatar = type === 'user' ? '👤' : '🎯';
        var time = timestamp
            ? new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
            : new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

        messageDiv.innerHTML = '<div class="message-avatar">' + avatar + '</div><div class="message-content">' + content + '<div class="message-time">' + time + '</div></div>';
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
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
});
