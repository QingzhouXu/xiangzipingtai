document.addEventListener('DOMContentLoaded', () => {
    const currentMerchantId = document.body.dataset.merchantId || 'tea_shop';

    // 表单元素
    const storeNameInput = document.getElementById('store-name');
    const storeSloganTextarea = document.getElementById('store-slogan');
    const storeCategoryInput = document.getElementById('store-category');
    const storeHoursInput = document.getElementById('store-hours');
    const storeAddressInput = document.getElementById('store-address');
    const resetButton = document.getElementById('reset-btn');
    const saveButton = document.getElementById('save-btn');

    // 图片上传元素
    const coverUpload = document.querySelector('.upload-box');
    const avatarUpload = document.querySelector('.upload-box.small');

    // 存储上传的图片数据（base64）
    let uploadedCover = null;
    let uploadedAvatar = null;

    // 原始数据备份
    let originalData = {
        name: storeNameInput ? storeNameInput.value : '',
        slogan: storeSloganTextarea ? storeSloganTextarea.value : '',
        category: storeCategoryInput ? storeCategoryInput.value : '',
        hours: storeHoursInput ? storeHoursInput.value : '',
        address: storeAddressInput ? storeAddressInput.value : ''
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
                    previewImage(coverUpload, file, function(base64) {
                        uploadedCover = base64;
                    });
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
                    previewImage(avatarUpload, file, function(base64) {
                        uploadedAvatar = base64;
                    });
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
                if (storeCategoryInput) storeCategoryInput.value = originalData.category;
                if (storeHoursInput) storeHoursInput.value = originalData.hours;
                if (storeAddressInput) storeAddressInput.value = originalData.address;
                // 重置图片预览
                const coverPreview = coverUpload?.querySelector('img');
                const avatarPreview = avatarUpload?.querySelector('img');
                if (coverPreview) coverPreview.remove();
                if (avatarPreview) avatarPreview.remove();
                uploadedCover = null;
                uploadedAvatar = null;

                showMessage('已撤销所有修改', 'info');
            }
        });
    }

    // ── 资料导入功能 ──
    const importBtn = document.getElementById('import-btn');
    const importText = document.getElementById('import-text');
    const importStatus = document.getElementById('import-status');
    const importResult = document.getElementById('import-result');
    const importList = document.getElementById('import-knowledge-list');

    if (importBtn && importText) {
        importBtn.addEventListener('click', async () => {
            const text = importText.value.trim();
            if (!text) {
                showMessage('请先输入店铺资料', 'error');
                return;
            }

            importBtn.disabled = true;
            importBtn.textContent = '正在生成知识库...';
            importStatus.textContent = 'AI 正在分析资料...';

            try {
                const response = await fetch('/api/merchant/import-data', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        merchant_id: currentMerchantId,
                        raw_text: text
                    })
                });

                const data = await response.json();

                if (data.success) {
                    showMessage('知识库生成成功！', 'success');
                    importStatus.textContent = `导入完成，生成 ${data.count} 条知识`;

                    // 显示生成结果
                    importResult.style.display = 'block';
                    importList.innerHTML = '';
                    data.items.forEach((item) => {
                        const li = document.createElement('li');
                        li.style.cssText = 'padding: 8px 12px; margin: 4px 0; background: var(--surface); border-radius: 6px; border-left: 3px solid var(--primary);';
                        li.innerHTML = `
                            <strong style="font-size: 13px;">${item.question}</strong>
                            <p style="margin: 4px 0 0; font-size: 12px; color: var(--muted);">${item.answer}</p>
                        `;
                        importList.appendChild(li);
                    });
                } else {
                    showMessage(data.error || '导入失败', 'error');
                    importStatus.textContent = '导入失败，请重试';
                }
            } catch (error) {
                console.error('导入失败:', error);
                showMessage('网络错误，请稍后重试', 'error');
                importStatus.textContent = '网络错误';
            } finally {
                importBtn.disabled = false;
                importBtn.textContent = '导入并生成知识库';
            }
        });
    }

    // 保存按钮功能
    if (saveButton) {
        saveButton.addEventListener('click', async () => {
            const formData = {
                merchant_id: currentMerchantId,
                name: storeNameInput ? storeNameInput.value.trim() : '',
                slogan: storeSloganTextarea ? storeSloganTextarea.value.trim() : '',
                category: storeCategoryInput ? storeCategoryInput.value.trim() : '',
                hours: storeHoursInput ? storeHoursInput.value.trim() : '',
                address: storeAddressInput ? storeAddressInput.value.trim() : ''
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

            // 添加上传的图片数据
            if (uploadedCover) formData.cover_image = uploadedCover;
            if (uploadedAvatar) formData.avatar_image = uploadedAvatar;

            try {
                saveButton.disabled = true;
                saveButton.textContent = '保存中...';

                const response = await fetch('/api/merchant/store', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });

                const data = await response.json();

                if (data.success) {
                    originalData = {
                        name: formData.name,
                        slogan: formData.slogan,
                        category: formData.category,
                        hours: formData.hours,
                        address: formData.address
                    };
                    uploadedCover = null;
                    uploadedAvatar = null;
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

    // 图片预览功能（回调返回 base64 数据）
    function previewImage(container, file, callback) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const base64Data = e.target.result;

            // 移除已存在的预览图
            const existingImg = container.querySelector('img');
            if (existingImg) existingImg.remove();

            // 创建新的预览图
            const img = document.createElement('img');
            img.src = base64Data;
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

            // 回调返回 base64 数据
            if (callback) callback(base64Data);
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
