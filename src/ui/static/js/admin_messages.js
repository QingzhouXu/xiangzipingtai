document.addEventListener('DOMContentLoaded', () => {
    const currentMerchantId = document.body.dataset.merchantId || 'tea_shop';
    
    // 工具栏元素
    const allMessagesBtn = document.querySelector('.message-toolbar .primary-action');
    const unreadMessagesBtn = document.querySelector('.message-toolbar .soft-button');
    const searchInput = document.querySelector('.message-toolbar input');
    const searchBtn = document.querySelector('.message-toolbar button:last-child');
    
    // 消息表格
    const messageTable = document.querySelector('.message-table');
    
    // 当前筛选状态
    let currentFilter = 'all'; // 'all' 或 'unread'
    let currentSearch = '';
    
    // 消息数据（从API加载）
    let messages = [];
    
    // 初始化事件监听
    initEventListeners();
    
    // 加载消息列表
    loadMessages();
    
    function initEventListeners() {
        // 全部咨询按钮
        if (allMessagesBtn) {
            allMessagesBtn.addEventListener('click', () => {
                currentFilter = 'all';
                updateButtonStates();
                loadMessages();
            });
        }
        
        // 未读咨询按钮
        if (unreadMessagesBtn) {
            unreadMessagesBtn.addEventListener('click', () => {
                currentFilter = 'unread';
                updateButtonStates();
                loadMessages();
            });
        }
        
        // 搜索按钮
        if (searchBtn) {
            searchBtn.addEventListener('click', () => {
                currentSearch = searchInput ? searchInput.value.trim() : '';
                loadMessages();
            });
        }
        
        // 搜索输入框回车
        if (searchInput) {
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    currentSearch = searchInput.value.trim();
                    loadMessages();
                }
            });
        }
    }
    
    function updateButtonStates() {
        if (allMessagesBtn && unreadMessagesBtn) {
            if (currentFilter === 'all') {
                allMessagesBtn.className = 'primary-action';
                unreadMessagesBtn.className = 'soft-button';
            } else {
                allMessagesBtn.className = 'soft-button';
                unreadMessagesBtn.className = 'primary-action';
            }
        }
    }
    
    function loadMessages() {
        fetch('/api/merchant/messages?merchant_id=' + encodeURIComponent(currentMerchantId) + '&filter=' + encodeURIComponent(currentFilter) + '&search=' + encodeURIComponent(currentSearch))
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.success) {
                    messages = data.messages || [];
                    renderMessageTable(messages);
                } else {
                    renderMessageTable([]);
                }
            })
            .catch(function(error) {
                console.error('加载消息失败:', error);
                showMessage('加载消息失败，请刷新页面重试', 'error');
            });
    }
    
    function renderMessageTable(messageList) {
        if (!messageTable) return;
        
        // 保留表头
        const headerRow = messageTable.querySelector('.header');
        messageTable.innerHTML = '';
        if (headerRow) {
            messageTable.appendChild(headerRow);
        }
        
        if (messageList.length === 0) {
            const emptyRow = document.createElement('div');
            emptyRow.className = 'table-row empty';
            emptyRow.innerHTML = '<span colspan="5">暂无咨询记录</span>';
            messageTable.appendChild(emptyRow);
            return;
        }
        
        messageList.forEach(message => {
            const row = document.createElement('div');
            row.className = 'table-row';
            row.innerHTML = `
                <span>${escapeHtml(message.visitor)}</span>
                <span>${escapeHtml(message.content)}</span>
                <span>${message.time}</span>
                <span class="${message.status === 'unread' ? 'unread' : 'read'}">${message.status === 'unread' ? '未读' : '已读'}</span>
                <button class="detail-btn" data-id="${message.id}">查看详情</button>
            `;
            
            // 添加查看详情事件
            const detailBtn = row.querySelector('.detail-btn');
            if (detailBtn) {
                detailBtn.addEventListener('click', () => showMessageDetail(message));
            }
            
            messageTable.appendChild(row);
        });
    }
    
    function showMessageDetail(message) {
        // 创建详情弹窗
        const modal = document.createElement('div');
        modal.className = 'message-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        `;
        
        const modalContent = document.createElement('div');
        modalContent.style.cssText = `
            background: white;
            border-radius: 8px;
            padding: 24px;
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            position: relative;
        `;
        
        modalContent.innerHTML = `
            <h3>咨询详情</h3>
            <div style="margin: 16px 0;">
                <p><strong>访客：</strong>${escapeHtml(message.visitor)}</p>
                <p><strong>时间：</strong>${message.time}</p>
                <p><strong>状态：</strong><span class="${message.status === 'unread' ? 'unread' : 'read'}">${message.status === 'unread' ? '未读' : '已读'}</span></p>
                <div style="margin-top: 16px;">
                    <strong>咨询内容：</strong>
                    <p style="background: #f8f9fa; padding: 12px; border-radius: 4px; margin-top: 8px;">${escapeHtml(message.content)}</p>
                </div>
            </div>
            <div style="text-align: right; margin-top: 20px;">
                ${message.status === 'unread' ? '<button class="mark-read-btn primary-action" style="margin-right: 8px;">标记为已读</button>' : ''}
                <button class="close-modal-btn soft-button">关闭</button>
            </div>
        `;
        
        modal.appendChild(modalContent);
        document.body.appendChild(modal);
        
        // 添加事件监听
        const closeBtn = modalContent.querySelector('.close-modal-btn');
        const markReadBtn = modalContent.querySelector('.mark-read-btn');
        
        closeBtn.addEventListener('click', () => {
            document.body.removeChild(modal);
        });
        
        if (markReadBtn) {
            markReadBtn.addEventListener('click', function() {
                fetch('/api/merchant/messages/' + message.id + '/read', { method: 'POST' })
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        if (data.success) {
                            var msgIndex = messages.findIndex(function(m) { return m.id === message.id; });
                            if (msgIndex !== -1) {
                                messages[msgIndex].status = 'read';
                            }
                            document.body.removeChild(modal);
                            loadMessages();
                            showMessage('已标记为已读', 'success');
                        } else {
                            showMessage('操作失败，请重试', 'error');
                        }
                    })
                    .catch(function() {
                        showMessage('操作失败，请重试', 'error');
                    });
            });
        }
        
        // 点击背景关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        });
    }
    
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    function showMessage(message, type = 'info') {
        // 移除已存在的消息
        const existingMessage = document.querySelector('.message-toast');
        if (existingMessage) existingMessage.remove();
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message-toast ${type}`;
        messageDiv.textContent = message;
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 6px;
            color: white;
            font-size: 14px;
            z-index: 9999;
            transition: all 0.3s ease;
            transform: translateX(100%);
        `;
        
        // 设置背景色
        switch (type) {
            case 'success':
                messageDiv.style.backgroundColor = '#28a745';
                break;
            case 'error':
                messageDiv.style.backgroundColor = '#dc3545';
                break;
            case 'info':
                messageDiv.style.backgroundColor = '#17a2b8';
                break;
        }
        
        document.body.appendChild(messageDiv);
        
        // 显示动画
        setTimeout(() => {
            messageDiv.style.transform = 'translateX(0)';
        }, 100);
        
        // 自动隐藏
        setTimeout(() => {
            messageDiv.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 300);
        }, 3000);
    }
});
