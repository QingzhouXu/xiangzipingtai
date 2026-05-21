document.addEventListener('DOMContentLoaded', () => {
    const currentMerchantId = document.body.dataset.merchantId || 'tea_shop';

    const syncInfoBtn = document.querySelector('.merchant-panel button.soft-button');
    const generatePersonaBtn = document.querySelector('.merchant-panel button.primary-action');
    const regenerateBtn = document.querySelector('.persona-result button.soft-button');
    const savePersonaBtn = document.querySelector('.persona-result button.primary-action');

    const personaPreview = document.querySelector('.persona-preview');
    const personaName = document.querySelector('.persona-result h3');
    const personaDesc = document.querySelector('.persona-result p.muted-text');

    // 形象图片相关元素
    const personaImageUpload = document.getElementById('persona-image-upload');
    const personaImageInput = document.getElementById('persona-image-input');
    const personaImagePreview = document.getElementById('persona-image-preview');
    const personaImagePlaceholder = document.getElementById('persona-image-placeholder');
    const generateImageBtn = document.getElementById('generate-image-btn');
    const imageStatus = document.getElementById('image-status');
    const previewEmoji = document.getElementById('preview-emoji');
    const previewImageContainer = document.getElementById('persona-preview-image');

    let currentPersona = {
        name: '',
        description: '',
        avatar: '🤖',
        image: '',
        generated: false
    };

    init();
    initEventListeners();
    initImageUpload();

    async function init() {
        try {
            const response = await fetch(`/api/merchant/persona?merchant=${encodeURIComponent(currentMerchantId)}`);
            const data = await response.json();
            if (data.persona && data.persona.name) {
                currentPersona = { ...data.persona, generated: true };
                updatePersonaPreview(currentPersona.name, currentPersona.description, true, currentPersona.avatar || '🤖', currentPersona.image || '');
            }
        } catch (e) {
            // No saved persona yet — that's fine
        }
    }

    function initImageUpload() {
        if (!personaImageUpload || !personaImageInput) return;

        personaImageUpload.addEventListener('click', () => {
            personaImageInput.click();
        });

        personaImageInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (ev) => {
                const dataUrl = ev.target.result;

                // 显示预览
                personaImagePreview.innerHTML = `<img src="${dataUrl}" alt="形象图片">`;
                personaImagePlaceholder.style.display = 'none';

                // 保存到当前形象
                currentPersona.image = dataUrl;
                if (imageStatus) imageStatus.textContent = '✓ 已上传图片';
            };
            reader.readAsDataURL(file);
        });
    }

    function initEventListeners() {
        if (syncInfoBtn) {
            syncInfoBtn.addEventListener('click', () => syncStoreInfo());
        }

        if (generatePersonaBtn) {
            generatePersonaBtn.addEventListener('click', () => generatePersona());
        }

        if (regenerateBtn) {
            regenerateBtn.addEventListener('click', () => generatePersona());
        }

        if (savePersonaBtn) {
            savePersonaBtn.addEventListener('click', () => savePersona());
        }

        if (generateImageBtn) {
            generateImageBtn.addEventListener('click', () => generatePersonaImage());
        }
    }

    async function generatePersonaImage() {
        if (generateImageBtn) {
            generateImageBtn.disabled = true;
            generateImageBtn.textContent = '生成中...';
        }
        if (imageStatus) imageStatus.textContent = 'AI 正在生成图片...';

        try {
            const response = await fetch('/api/merchant/persona/generate-image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ merchant_id: currentMerchantId })
            });

            const data = await response.json();

            if (data.success && data.image_url) {
                // 显示生成的图片
                personaImagePreview.innerHTML = `<img src="${data.image_url}" alt="AI形象图片">`;
                personaImagePlaceholder.style.display = 'none';

                currentPersona.image = data.image_url;

                // 同步更新预览
                if (previewImageContainer) {
                    previewImageContainer.innerHTML = `<img src="${data.image_url}" alt="预览">`;
                    if (previewEmoji) previewEmoji.style.display = 'none';
                }

                if (imageStatus) imageStatus.textContent = '✓ 图片生成成功';
            } else {
                // 如果AI生成失败，提示手动上传
                if (imageStatus) imageStatus.textContent = data.error || 'AI图片生成失败，请手动上传';
            }
        } catch (error) {
            console.error('生成形象图片失败:', error);
            if (imageStatus) imageStatus.textContent = '生成失败，请手动上传图片';
        } finally {
            if (generateImageBtn) {
                generateImageBtn.disabled = false;
                generateImageBtn.textContent = 'AI生成形象图片';
            }
        }
    }

    async function syncStoreInfo() {
        try {
            syncInfoBtn.disabled = true;
            syncInfoBtn.textContent = '同步中...';

            const response = await fetch(`/api/knowledge?merchant=${encodeURIComponent(currentMerchantId)}`);
            const data = await response.json();

            if (data.merchant) {
                showMessage('店铺信息同步成功', 'success');
            } else {
                showMessage('店铺信息同步失败', 'error');
            }
        } catch (error) {
            console.error('同步店铺信息失败:', error);
            showMessage('网络错误，请稍后重试', 'error');
        } finally {
            syncInfoBtn.disabled = false;
            syncInfoBtn.textContent = '同步店铺信息';
        }
    }

    async function generatePersona() {
        try {
            if (generatePersonaBtn) {
                generatePersonaBtn.disabled = true;
                generatePersonaBtn.textContent = '生成中...';
            }
            if (regenerateBtn) {
                regenerateBtn.disabled = true;
                regenerateBtn.textContent = '生成中...';
            }

            showMessage('正在基于店铺信息生成AI形象...', 'info');

            const response = await fetch('/api/merchant/persona/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ merchant_id: currentMerchantId })
            });

            const data = await response.json();

            if (data.success && data.persona) {
                const p = data.persona;
                currentPersona = {
                    name: p.name,
                    description: p.description,
                    avatar: p.avatar || '🤖',
                    image: currentPersona.image || p.image || '',
                    generated: true
                };
                updatePersonaPreview(p.name, p.description, true, p.avatar || '🤖', currentPersona.image);
                showMessage(data.fallback ? 'AI形象生成成功（本地模板）' : 'AI形象生成成功', 'success');
            } else {
                showMessage(data.error || '生成失败', 'error');
            }
        } catch (error) {
            console.error('生成AI形象失败:', error);
            showMessage('生成失败，请稍后重试', 'error');
        } finally {
            if (generatePersonaBtn) {
                generatePersonaBtn.disabled = false;
                generatePersonaBtn.textContent = '一键生成AI形象';
            }
            if (regenerateBtn) {
                regenerateBtn.disabled = false;
                regenerateBtn.textContent = '重新生成';
            }
        }
    }

    async function savePersona() {
        if (!currentPersona.generated) {
            showMessage('请先生成AI形象', 'error');
            return;
        }

        try {
            savePersonaBtn.disabled = true;
            savePersonaBtn.textContent = '保存中...';

            const response = await fetch('/api/merchant/persona', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    merchant_id: currentMerchantId,
                    persona: currentPersona
                })
            });

            const data = await response.json();

            if (data.success) {
                showMessage('AI形象保存成功并已上架展示', 'success');
                if (savePersonaBtn) {
                    savePersonaBtn.textContent = '已保存';
                    savePersonaBtn.disabled = true;
                }
            } else {
                showMessage(data.error || '保存失败', 'error');
            }
        } catch (error) {
            console.error('保存AI形象失败:', error);
            showMessage('网络错误，请稍后重试', 'error');
        } finally {
            if (savePersonaBtn && savePersonaBtn.textContent !== '已保存') {
                savePersonaBtn.disabled = false;
                savePersonaBtn.textContent = '保存并上架展示';
            }
        }
    }

    function updatePersonaPreview(name, description, generated, avatar, image) {
        if (personaName) {
            personaName.textContent = `已生成形象：${name}`;
        }

        if (personaDesc) {
            personaDesc.textContent = description;
        }

        if (personaPreview) {
            if (image) {
                personaPreview.innerHTML = `
                    <div class="persona-preview-image">
                        <img src="${image}" alt="AI形象预览">
                    </div>
                    <span>AI形象预览</span>
                `;
            } else {
                personaPreview.innerHTML = `
                    <div class="persona-preview-image">
                        <span style="font-size: 48px;">${avatar || '🤖'}</span>
                    </div>
                    <span>AI形象预览</span>
                `;
            }
        }

        // 同步更新上传区域预览
        if (image && personaImagePreview) {
            personaImagePreview.innerHTML = `<img src="${image}" alt="形象图片">`;
            if (personaImagePlaceholder) personaImagePlaceholder.style.display = 'none';
        }

        if (generated) {
            if (regenerateBtn) {
                regenerateBtn.style.display = 'inline-block';
            }
            if (savePersonaBtn) {
                savePersonaBtn.disabled = false;
                savePersonaBtn.textContent = '保存并上架展示';
            }
        }
    }

    function showMessage(message, type) {
        var existingMessage = document.querySelector('.message-toast');
        if (existingMessage) existingMessage.remove();

        var messageDiv = document.createElement('div');
        messageDiv.className = 'message-toast ' + type;
        messageDiv.textContent = message;
        messageDiv.style.cssText = [
            'position: fixed',
            'top: 20px',
            'right: 20px',
            'padding: 12px 20px',
            'border-radius: 6px',
            'color: white',
            'font-size: 14px',
            'z-index: 9999',
            'transition: all 0.3s ease',
            'transform: translateX(100%)'
        ].join(';');

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

        setTimeout(function() {
            messageDiv.style.transform = 'translateX(0)';
        }, 100);

        setTimeout(function() {
            messageDiv.style.transform = 'translateX(100%)';
            setTimeout(function() {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 300);
        }, 3000);
    }
});
