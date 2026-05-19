var favStorageKey = (window.__currentUser || 'anonymous') + '_favorites';

// 清理匿名用户的残留收藏（已登录用户）
if (window.__currentUser && window.__currentUser !== 'anonymous') {
    localStorage.removeItem('anonymous_favorites');
}

document.addEventListener('DOMContentLoaded', () => {
    // 获取DOM元素
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const filterBtns = document.querySelectorAll('.category-item-dark');
    const shopGrid = document.getElementById('shop-grid');
    const sidebar = document.querySelector('.category-sidebar');

    // 当前筛选状态
    let currentCategory = 'all';
    let currentSearch = '';
    let favorites = JSON.parse(localStorage.getItem(favStorageKey) || '[]');
    
    // 初始化
    initEventListeners();
    updateFavoriteButtons();
    
    function initEventListeners() {
        // 搜索功能
        if (searchBtn) {
            searchBtn.addEventListener('click', performSearch);
        }
        
        if (searchInput) {
            searchInput.addEventListener('input', handleSearchInput);
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    performSearch();
                }
            });
        }
        
        // 分类筛选
        filterBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                filterBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentCategory = btn.dataset.category;
                filterMerchants();
            });
        });
        
        // 收藏按钮事件委托
        if (shopGrid) {
            shopGrid.addEventListener('click', (e) => {
                if (e.target.closest('.favorite-btn')) {
                    const btn = e.target.closest('.favorite-btn');
                    toggleFavorite(btn);
                }
            });
        }
    }
    
    function handleSearchInput() {
        var loader = document.getElementById('search-loader');
        var searchIcon = document.querySelector('.search-icon');

        if (searchInput.value.trim()) {
            if (loader) loader.classList.add('active');
            if (searchIcon) searchIcon.style.display = 'none';
        } else {
            if (loader) loader.classList.remove('active');
            if (searchIcon) searchIcon.style.display = 'flex';
        }
    }
    
    function performSearch() {
        currentSearch = searchInput ? searchInput.value.trim() : '';
        filterMerchants();
    }
    
    var filterTimer = null;

    function filterMerchants() {
        if (filterTimer) {
            clearTimeout(filterTimer);
            filterTimer = null;
        }

        var shopCards = document.querySelectorAll('.shop-card-horizontal');

        shopCards.forEach(function(card) {
            card.classList.remove('shop-card-fading', 'shop-card-showing');
        });

        var hidingCards = [];
        var showingCards = [];

        shopCards.forEach(function(card) {
            var merchantName = card.querySelector('h3').textContent.toLowerCase();
            var merchantCategory = card.querySelector('.category-tag').textContent.toLowerCase();
            var merchantSlogan = card.querySelector('.slogan').textContent.toLowerCase();

            var categoryMatch = currentCategory === 'all' || merchantCategory.includes(currentCategory.toLowerCase());
            var searchMatch = !currentSearch ||
                merchantName.includes(currentSearch.toLowerCase()) ||
                merchantCategory.includes(currentSearch.toLowerCase()) ||
                merchantSlogan.includes(currentSearch.toLowerCase());

            var shouldShow = categoryMatch && searchMatch;
            var isHidden = card.classList.contains('shop-card-hidden');

            if (shouldShow && isHidden) {
                showingCards.push(card);
            } else if (!shouldShow && !isHidden) {
                hidingCards.push(card);
            }
        });

        if (hidingCards.length === 0 && showingCards.length === 0) {
            checkNoResults();
            return;
        }

        hidingCards.forEach(function(card) {
            card.classList.add('shop-card-fading');
        });

        filterTimer = setTimeout(function() {
            filterTimer = null;

            hidingCards.forEach(function(card) {
                card.classList.add('shop-card-hidden');
                card.classList.remove('shop-card-fading');
            });

            showingCards.forEach(function(card) {
                card.classList.remove('shop-card-hidden');
                card.classList.add('shop-card-showing');
            });

            requestAnimationFrame(function() {
                requestAnimationFrame(function() {
                    showingCards.forEach(function(card) {
                        card.classList.remove('shop-card-showing');
                    });
                    checkNoResults();
                });
            });
        }, 420);
    }
    
    function checkNoResults() {
        var visibleCards = document.querySelectorAll('.shop-card-horizontal:not(.shop-card-hidden)');
        var noResultsMsg = document.querySelector('.no-results');
        
        if (visibleCards.length === 0) {
            if (!noResultsMsg) {
                noResultsMsg = document.createElement('div');
                noResultsMsg.className = 'no-results';
                noResultsMsg.innerHTML = `
                    <div style="text-align: center; padding: 40px; color: var(--muted-foreground);">
                        <div style="font-size: 48px; margin-bottom: 16px;">🔍</div>
                        <h3>没有找到相关店铺</h3>
                        <p>试试调整搜索关键词或选择其他分类</p>
                    </div>
                `;
                shopGrid.appendChild(noResultsMsg);
            }
        } else if (noResultsMsg) {
            noResultsMsg.remove();
        }
    }
    
    function toggleFavorite(btn) {
        const merchantId = btn.dataset.merchantId;
        const merchantName = btn.dataset.merchantName;
        
        const index = favorites.findIndex(fav => fav.merchantId === merchantId);
        
        if (index === -1) {
            // 添加到收藏
            favorites.push({
                merchantId,
                merchantName,
                addedAt: new Date().toISOString()
            });
            btn.classList.add('favorited');
            showMessage(`已收藏 ${merchantName}`, 'success');
        } else {
            // 从收藏中移除
            favorites.splice(index, 1);
            btn.classList.remove('favorited');
            showMessage(`已取消收藏 ${merchantName}`, 'info');
        }
        
        // 保存到本地存储
        localStorage.setItem(favStorageKey, JSON.stringify(favorites));
    }
    
    function updateFavoriteButtons() {
        const favoriteBtns = document.querySelectorAll('.favorite-btn');
        
        favoriteBtns.forEach(btn => {
            const merchantId = btn.dataset.merchantId;
            
            if (favorites.some(fav => fav.merchantId === merchantId)) {
                btn.classList.add('favorited');
            } else {
                btn.classList.remove('favorited');
            }
        });
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

// 收藏页面功能
function showFavoritesPage() {
    const favorites = JSON.parse(localStorage.getItem(favStorageKey) || '[]');
    
    // 创建收藏页面模态框
    const modal = document.createElement('div');
    modal.className = 'favorites-modal';
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
        background: var(--card);
        border-radius: 8px;
        padding: 24px;
        max-width: 800px;
        width: 90%;
        max-height: 80vh;
        overflow-y: auto;
        position: relative;
        color: var(--foreground);
    `;
    
    let favoritesHTML = '';
    if (favorites.length === 0) {
        favoritesHTML = `
            <div style="text-align: center; padding: 40px; color: #666;">
                <div style="font-size: 48px; margin-bottom: 16px;">🤍</div>
                <h3>还没有收藏的店铺</h3>
                <p>去首页浏览并收藏你喜欢的店铺吧</p>
            </div>
        `;
    } else {
        favoritesHTML = '<div class="favorites-grid">';
        favorites.forEach(fav => {
            favoritesHTML += `
                <div class="favorite-item">
                    <h4>${fav.merchantName}</h4>
                    <p>收藏时间：${new Date(fav.addedAt).toLocaleDateString()}</p>
                    <div class="favorite-actions">
                        <button class="primary-action" onclick="goToChat('${fav.merchantId}')">进店咨询</button>
                        <button class="danger-outline" onclick="removeFavorite('${fav.merchantId}', this)">取消收藏</button>
                    </div>
                </div>
            `;
        });
        favoritesHTML += '</div>';
    }
    
    modalContent.innerHTML = `
        <h3>我的收藏 (${favorites.length})</h3>
        ${favoritesHTML}
        <div style="text-align: right; margin-top: 20px;">
            <button class="soft-button" onclick="closeFavoritesModal()">关闭</button>
        </div>
    `;
    
    modal.appendChild(modalContent);
    document.body.appendChild(modal);
    
    // 点击背景关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    });
    
    // 全局函数
    window.closeFavoritesModal = () => {
        document.body.removeChild(modal);
    };
    
    window.goToChat = (merchantId) => {
        window.location.href = `/chat?merchant=${merchantId}`;
    };
    
    window.removeFavorite = (merchantId, btn) => {
        let favorites = JSON.parse(localStorage.getItem(favStorageKey) || '[]');
        favorites = favorites.filter(fav => fav.merchantId !== merchantId);
        localStorage.setItem(favStorageKey, JSON.stringify(favorites));
        
        // 移除收藏项
        const favoriteItem = btn.closest('.favorite-item');
        favoriteItem.remove();
        
        // 更新计数
        const title = modalContent.querySelector('h3');
        title.textContent = `我的收藏 (${favorites.length})`;
        
        // 如果没有收藏了，显示空状态
        if (favorites.length === 0) {
            const grid = modalContent.querySelector('.favorites-grid');
            grid.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #666;">
                    <div style="font-size: 48px; margin-bottom: 16px;">🤍</div>
                    <h3>还没有收藏的店铺</h3>
                    <p>去首页浏览并收藏你喜欢的店铺吧</p>
                </div>
            `;
        }
        
        showMessage('已取消收藏', 'info');
        
        // 更新首页收藏按钮状态
        const favoriteBtn = document.querySelector(`[data-merchant-id="${merchantId}"]`);
        if (favoriteBtn) {
            favoriteBtn.classList.remove('favorited');
        }
    };
}

// ── 3D tilt effect for shop cards ──
(function() {
    function applyTilt(elements) {
        elements.forEach(function(card) {
            var rafId = null;
            var targetRx = 0, targetRy = 0;
            var currentRx = 0, currentRy = 0;

            card.addEventListener('mousemove', function(e) {
                var rect = card.getBoundingClientRect();
                targetRx = ((e.clientY - rect.top) / rect.height - 0.5) * -5;
                targetRy = ((e.clientX - rect.left) / rect.width - 0.5) * 5;
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

    applyTilt(document.querySelectorAll('.shop-card-horizontal'));

    // ── Sidebar tilt: events on stable outer, tilt on inner (no feedback loop) ──
    var sidebar = document.querySelector('.category-sidebar');
    var sidebarInner = document.querySelector('.sidebar-tilt-inner');
    if (sidebar && sidebarInner) {
        var sRaf = null;
        var sTx = 0, sTy = 0;
        var sCx = 0, sCy = 0;

        sidebar.addEventListener('mousemove', function(e) {
            var rect = sidebar.getBoundingClientRect();
            sTx = ((e.clientY - rect.top) / rect.height - 0.5) * -10;
            sTy = ((e.clientX - rect.left) / rect.width - 0.5) * 10;
            if (!sRaf) sRaf = requestAnimationFrame(sUpdate);
        });

        sidebar.addEventListener('mouseleave', function() {
            sTx = 0;
            sTy = 0;
            if (!sRaf) sRaf = requestAnimationFrame(sUpdate);
        });

        function sUpdate() {
            sCx += (sTx - sCx) * 0.12;
            sCy += (sTy - sCy) * 0.12;

            var settled = Math.abs(sTx - sCx) < 0.01 && Math.abs(sTy - sCy) < 0.01;

            if (settled && sTx === 0 && sTy === 0) {
                sidebarInner.style.transform = '';
                sRaf = null;
            } else if (settled) {
                sidebarInner.style.transform = 'perspective(1200px) rotateX(' + sTx.toFixed(2) + 'deg) rotateY(' + sTy.toFixed(2) + 'deg)';
                sRaf = null;
            } else {
                sidebarInner.style.transform = 'perspective(1200px) rotateX(' + sCx.toFixed(2) + 'deg) rotateY(' + sCy.toFixed(2) + 'deg)';
                sRaf = requestAnimationFrame(sUpdate);
            }
        }
    }
})();
