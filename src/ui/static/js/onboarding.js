document.addEventListener('DOMContentLoaded', () => {
    initFileUpload();
});

function initFileUpload() {
    // 头像上传
    const avatarUpload = document.getElementById('avatar-upload');
    const avatarInput = document.getElementById('avatar-input');
    const avatarPreview = document.getElementById('avatar-preview');
    const avatarData = document.getElementById('avatar-data');
    
    if (avatarUpload && avatarInput) {
        avatarUpload.addEventListener('click', () => {
            avatarInput.click();
        });
        
        avatarInput.addEventListener('change', (e) => {
            handleFileSelect(e.target.files[0], 'avatar');
        });
    }
    
    // 资质文件上传
    const licenseUpload = document.getElementById('license-upload');
    const licenseInput = document.getElementById('license-input');
    const licenseFilename = document.getElementById('license-filename');
    const licenseData = document.getElementById('license-data');
    
    if (licenseUpload && licenseInput) {
        licenseUpload.addEventListener('click', () => {
            licenseInput.click();
        });
        
        licenseInput.addEventListener('change', (e) => {
            handleFileSelect(e.target.files[0], 'license');
        });
    }
}

function handleFileSelect(file, type) {
    if (!file) return;
    
    // 检查文件大小（限制为5MB）
    const maxSize = 5 * 1024 * 1024;
    if (file.size > maxSize) {
        showMessage('文件大小不能超过5MB', 'error');
        return;
    }
    
    // 读取文件并转换为base64
    const reader = new FileReader();
    reader.onload = (e) => {
        const base64Data = e.target.result;
        
        if (type === 'avatar') {
            // 上传后让图片填满整个上传区域
            const uploadDiv = document.getElementById('avatar-upload');
            uploadDiv.style.display = 'flex';
            uploadDiv.style.alignItems = 'center';
            uploadDiv.style.justifyContent = 'center';
            uploadDiv.style.width = '150px';
            uploadDiv.style.height = '150px';
            uploadDiv.style.borderRadius = '50%';
            uploadDiv.style.overflow = 'hidden';
            uploadDiv.innerHTML = `<img src="${base64Data}" style="width: 100%; height: 100%; object-fit: cover; display: block;">`;

            // 保存数据
            const avatarData = document.getElementById('avatar-data');
            avatarData.value = base64Data;

            showMessage('头像上传成功', 'success');
        } else if (type === 'license') {
            // 显示文件名
            const licenseFilename = document.getElementById('license-filename');
            licenseFilename.textContent = `✓ ${file.name}`;
            licenseFilename.style.color = '#28a745';
            
            // 保存数据
            const licenseData = document.getElementById('license-data');
            licenseData.value = base64Data;
            
            showMessage('文件上传成功', 'success');
        }
    };
    
    reader.onerror = () => {
        showMessage('文件读取失败', 'error');
    };
    
    reader.readAsDataURL(file);
}

function showMessage(message, type = 'info') {
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
    
    setTimeout(() => {
        messageDiv.style.transform = 'translateX(0)';
    }, 100);
    
    setTimeout(() => {
        messageDiv.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.parentNode.removeChild(messageDiv);
            }
        }, 300);
    }, 3000);
}
