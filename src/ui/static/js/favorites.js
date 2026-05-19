document.addEventListener('DOMContentLoaded', () => {
    // 获取DOM元素
    const favoritesGrid = document.getElementById('favorites-grid');
    const favoritesCount = document.getElementById('favorites-count');
    const clearAllBtn = document.getElementById('clear-all-favorites');
    
    // 收藏数据
    let favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
    
    // 初始化
    loadFavorites();
    initEventListeners();
    
    function initEventListeners() {
        // 清空收藏
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', clearAllFavorites);
        }
        
        // 收藏按钮事件委托
        if (favoritesGrid) {
            favoritesGrid.addEventListener('click', (e) => {
                if (e.target.closest('.favorite-btn')) {
                    const btn = e.target.closest('.favorite-btn');
                    toggleFavorite(btn);
                }
                if (e.target.closest('.remove-favorite-btn')) {
                    const btn = e.target.closest('.remove-favorite-btn');
                    const merchantId = btn.dataset.merchantId;
                    removeFavorite(merchantId);
                }
                if (e.target.closest('.visit-merchant-btn')) {
                    const btn = e.target.closest('.visit-merchant-btn');
                    const merchantId = btn.dataset.merchantId;
                    visitMerchant(merchantId);
                }
            });
        }
    }
    
    function loadFavorites() {
        updateFavoritesCount();
        
        if (favorites.length === 0) {
            showEmptyState();
            return;
        }
        
        // 获取商户详细信息
        Promise.all(favorites.map(fav => getMerchantDetails(fav.merchantId)))
            .then(merchants => {
                renderFavorites(merchants.filter(m => m !== null));
            })
            .catch(error => {
                console.error('获取商户信息失败:', error);
                showErrorState();
            });
    }
    
    async function getMerchantDetails(merchantId) {
        try {
            // 使用不需要登录的API获取商户信息
            const response = await fetch('/api/merchants');
            const data = await response.json();
            
            if (data.merchants) {
                const merchant = data.merchants.find(m => m.id === merchantId);
                if (merchant) {
                    const favorite = favorites.find(fav => fav.merchantId === merchantId);
                    return {
                        ...merchant,
                        addedAt: favorite.addedAt
                    };
                }
            }
            return null;
        } catch (error) {
            console.error(`获取商户 ${merchantId} 信息失败:`, error);
            return null;
        }
    }
    
    function renderFavorites(merchants) {
        if (!favoritesGrid) return;
        
        let html = '<div class="favorites-grid-items">';
        
        merchants.forEach(merchant => {
            html += `
                <article class="favorite-card">
                    <div class="favorite-cover-wrapper">
                        <img src="${merchant.cover}" alt="${merchant.name}" class="favorite-cover">
                    </div>
                    <div class="favorite-card-body">
                        <h3>${merchant.name}</h3>
                        <div class="favorite-meta">
                            <span>${merchant.category}</span>
                            <span class="rating">⭐ ${merchant.rating}</span>
                        </div>
                        <p>${merchant.slogan}</p>
                        <div class="favorite-footer">
                            <small>收藏于 ${new Date(merchant.addedAt).toLocaleDateString()}</small>
                            <div class="favorite-actions">
                                <button class="visit-merchant-btn primary-action" data-merchant-id="${merchant.id}">
                                    进店咨询
                                </button>
                                <button class="remove-favorite-btn danger-outline" data-merchant-id="${merchant.id}">
                                    取消收藏
                                </button>
                            </div>
                        </div>
                    </div>
                </article>
            `;
        });
        
        html += '</div>';
        favoritesGrid.innerHTML = html;
    }
    
    function showEmptyState() {
        if (!favoritesGrid) return;
        
        favoritesGrid.innerHTML = `
            <div class="empty-favorites">
                <div style="text-align: center; padding: 40px; color: var(--muted-foreground);">
                    <div style="font-size: 48px; margin-bottom: 16px;">🤍</div>
                    <h3>还没有收藏的店铺</h3>
                    <p>去首页浏览并收藏你喜欢的店铺吧</p>
                    <a href="/" class="primary-action">去首页浏览</a>
                </div>
            </div>
        `;
    }
    
    function showErrorState() {
        if (!favoritesGrid) return;
        
        favoritesGrid.innerHTML = `
            <div class="error-favorites">
                <div style="text-align: center; padding: 40px; color: #dc3545;">
                    <div style="font-size: 48px; margin-bottom: 16px;">⚠️</div>
                    <h3>加载收藏失败</h3>
                    <p>请刷新页面重试</p>
                    <button class="primary-action" onclick="location.reload()">刷新页面</button>
                </div>
            </div>
        `;
    }
    
    function updateFavoritesCount() {
        if (favoritesCount) {
            favoritesCount.textContent = favorites.length;
        }
    }
    
    function toggleFavorite(btn) {
        const merchantId = btn.dataset.merchantId;
        const merchantName = btn.dataset.merchantName || '该店铺';
        const heartIcon = btn.querySelector('.heart-icon');
        
        const index = favorites.findIndex(fav => fav.merchantId === merchantId);
        
        if (index !== -1) {
            // 从收藏中移除
            favorites.splice(index, 1);
            localStorage.setItem('favorites', JSON.stringify(favorites));
            
            // 移除卡片
            const card = btn.closest('.favorite-card');
            if (card) {
                card.style.transform = 'scale(0.8)';
                card.style.opacity = '0';
                setTimeout(() => {
                    card.remove();
                    updateFavoritesCount();
                    
                    // 如果没有收藏了，显示空状态
                    if (favorites.length === 0) {
                        showEmptyState();
                    }
                }, 300);
            }
            
            showMessage(`已取消收藏 ${merchantName}`, 'info');
        }
    }
    
    function removeFavorite(merchantId) {
        if (!confirm('确定要取消收藏这个店铺吗？')) {
            return;
        }
        
        const index = favorites.findIndex(fav => fav.merchantId === merchantId);
        if (index !== -1) {
            favorites.splice(index, 1);
            localStorage.setItem('favorites', JSON.stringify(favorites));
            
            // 移除卡片
            const btn = document.querySelector(`[data-merchant-id="${merchantId}"]`);
            const card = btn.closest('.favorite-card');
            if (card) {
                card.style.transform = 'scale(0.8)';
                card.style.opacity = '0';
                setTimeout(() => {
                    card.remove();
                    updateFavoritesCount();
                    
                    // 如果没有收藏了，显示空状态
                    if (favorites.length === 0) {
                        showEmptyState();
                    }
                }, 300);
            }
            
            showMessage('已取消收藏', 'info');
        }
    }
    
    function visitMerchant(merchantId) {
        window.location.href = `/chat?merchant=${merchantId}`;
    }
    
    function clearAllFavorites() {
        if (favorites.length === 0) {
            showMessage('没有收藏需要清空', 'info');
            return;
        }
        
        if (!confirm(`确定要清空所有 ${favorites.length} 个收藏吗？此操作不可恢复。`)) {
            return;
        }
        
        favorites = [];
        localStorage.setItem('favorites', JSON.stringify(favorites));
        updateFavoritesCount();
        showEmptyState();
        showMessage('已清空所有收藏', 'success');
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
