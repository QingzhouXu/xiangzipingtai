document.addEventListener('DOMContentLoaded', () => {
    const currentMerchantId = document.body.dataset.merchantId || 'tea_shop';
    
    // 表单元素
    const storeNameInput = document.getElementById('store-name');
    const storeSloganTextarea = document.getElementById('store-slogan');
    const resetButton = document.querySelector('.form-actions .soft-button');
    const saveButton = document.querySelector('.form-actions .primary-action');
    
    // 图片上传元素
    const coverUpload = document.querySelector('.upload-box');
    const avatarUpload = document.querySelector('.upload-box.small');
    
    // 原始数据备份
    let originalData = {
        name: storeNameInput ? storeNameInput.value : '',
        slogan: storeSloganTextarea ? storeSloganTextarea.value : ''
    };
    
    // 图片上传处理
    if (coverUpload) {
        coverUpload.addEventListener('click', () => {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'image/*';
            input.onchange = (e) => {
                const file = e.target.files[0];
                if (file) {
                    previewImage(coverUpload, file);
                }
            };
            input.click();
        });
    }
    
    if (avatarUpload) {
        avatarUpload.addEventListener('click', () => {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'image/*';
            input.onchange = (e) => {
                const file = e.target.files[0];
                if (file) {
                    previewImage(avatarUpload, file);
                }
            };
            input.click();
        });
    }
    
    // 重置按钮功能
    if (resetButton) {
        resetButton.addEventListener('click', () => {
            if (confirm('确定要撤销所有修改吗？')) {
                if (storeNameInput) storeNameInput.value = originalData.name;
                if (storeSloganTextarea) storeSloganTextarea.value = originalData.slogan;
                
                // 重置图片预览
                const coverPreview = coverUpload?.querySelector('img');
                const avatarPreview = avatarUpload?.querySelector('img');
                if (coverPreview) coverPreview.remove();
                if (avatarPreview) avatarPreview.remove();
                
                showMessage('已撤销所有修改', 'info');
            }
        });
    }
    
    // 保存按钮功能
    if (saveButton) {
        saveButton.addEventListener('click', async () => {
            const formData = {
                name: storeNameInput ? storeNameInput.value.trim() : '',
                slogan: storeSloganTextarea ? storeSloganTextarea.value.trim() : ''
            };
            
            // 验证表单
            if (!formData.name) {
                showMessage('请填写店铺名称', 'error');
                return;
            }
            
            if (!formData.slogan) {
                showMessage('请填写店铺简介', 'error');
                return;
            }
            
            try {
                saveButton.disabled = true;
                saveButton.textContent = '保存中...';
                
                const response = await fetch('/api/merchant/store', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        merchant_id: currentMerchantId,
                        ...formData
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    originalData = { ...formData };
                    showMessage('店铺信息保存成功', 'success');
                } else {
                    showMessage(data.error || '保存失败', 'error');
                }
            } catch (error) {
                console.error('保存失败:', error);
                showMessage('网络错误，请稍后重试', 'error');
            } finally {
                saveButton.disabled = false;
                saveButton.textContent = '保存修改';
            }
        });
    }
    
    // 图片预览功能
    function previewImage(container, file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            // 移除已存在的预览图
            const existingImg = container.querySelector('img');
            if (existingImg) existingImg.remove();
            
            // 创建新的预览图
            const img = document.createElement('img');
            img.src = e.target.result;
            img.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                object-fit: cover;
                border-radius: 8px;
            `;
            
            container.style.position = 'relative';
            container.appendChild(img);
            
            // 调整文字层级
            const text = container.querySelector('span');
            const small = container.querySelector('small');
            if (text) text.style.zIndex = '1';
            if (small) small.style.zIndex = '1';
        };
        reader.readAsDataURL(file);
    }
    
    // 消息提示功能
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
