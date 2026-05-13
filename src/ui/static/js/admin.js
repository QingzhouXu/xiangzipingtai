document.addEventListener('DOMContentLoaded', () => {
    // 商家后台脚本：负责知识库 CRUD、商家切换和 RAG 命中测试。
    const merchantSelect = document.getElementById('merchant-select');
    const summary = document.getElementById('merchant-summary');
    const list = document.getElementById('knowledge-list');
    const questionInput = document.getElementById('knowledge-question');
    const answerInput = document.getElementById('knowledge-answer');
    const addButton = document.getElementById('add-knowledge');
    const ragQuestion = document.getElementById('rag-question');
    const ragResult = document.getElementById('rag-result');
    const testButton = document.getElementById('test-rag');

    startHeartbeat();
    loadKnowledge();

    merchantSelect.addEventListener('change', loadKnowledge);
    addButton.addEventListener('click', addKnowledge);
    testButton.addEventListener('click', testRag);

    async function loadKnowledge() {
        // 每次切换商家都重新读取数据，确保多商家知识隔离。
        const merchantId = merchantSelect.value;
        try {
            const response = await fetch(`/api/knowledge?merchant=${encodeURIComponent(merchantId)}`);
            const data = await response.json();
            summary.textContent = `${data.merchant.name} · ${data.knowledge.length} 条知识 · 数据已隔离`;
            list.innerHTML = '';
            data.knowledge.forEach((item) => {
                const row = document.createElement('div');
                row.className = 'knowledge-item';
                row.innerHTML = `
                    <div>
                        <strong>${escapeHtml(item.question)}</strong>
                        <p>${escapeHtml(item.answer)}</p>
                        <small>${escapeHtml(item.category || '知识')}</small>
                    </div>
                    <button data-id="${item.id}">删除</button>
                `;
                row.querySelector('button').addEventListener('click', () => deleteKnowledge(item.id));
                list.appendChild(row);
            });
        } catch (error) {
            summary.textContent = '知识库加载失败';
            console.error(error);
        }
    }

    async function addKnowledge() {
        // 新增知识会立即写入 JSON 文件，并重建后端 TF-IDF 向量。
        const question = questionInput.value.trim();
        const answer = answerInput.value.trim();
        if (!question || !answer) {
            alert('请填写问题和回答');
            return;
        }

        const response = await fetch('/api/knowledge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ merchant_id: merchantSelect.value, question, answer })
        });
        const data = await response.json();
        if (data.success) {
            questionInput.value = '';
            answerInput.value = '';
            await loadKnowledge();
        } else {
            alert(data.error || '新增失败');
        }
    }

    async function deleteKnowledge(id) {
        const response = await fetch(`/api/knowledge/${encodeURIComponent(id)}?merchant=${encodeURIComponent(merchantSelect.value)}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        if (data.success) {
            await loadKnowledge();
        } else {
            alert('删除失败');
        }
    }

    async function testRag() {
        // 后台演示用接口，会展示黄金路径或 TF-IDF 的真实命中结果。
        ragResult.textContent = '正在检索知识库...';
        try {
            const response = await fetch('/api/rag/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ merchant_id: merchantSelect.value, question: ragQuestion.value.trim() })
            });
            const data = await response.json();
            if (data.answer) {
                ragResult.innerHTML = `
                    <small>${data.source === 'golden' ? '黄金路径命中' : 'TF-IDF 命中'} · 相似度 ${Number(data.score).toFixed(2)}</small>
                    <strong>命中的知识：</strong>
                    <p>${escapeHtml(data.answer)}</p>
                `;
            } else {
                ragResult.textContent = data.message || '未命中知识库';
            }
        } catch (error) {
            ragResult.textContent = 'RAG 测试失败';
            console.error(error);
        }
    }

    function escapeHtml(value) {
        return String(value || '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }
});

function startHeartbeat() {
    // 后台同样展示开发板状态，让评委能看到边缘推理连接情况。
    const statusEl = document.getElementById('board-status');
    if (!statusEl) return;

    async function refresh() {
        try {
            const response = await fetch('/api/heartbeat');
            const data = await response.json();
            if (data.status === 'success') {
                statusEl.className = 'board-status online';
                statusEl.textContent = `🟢 开发板已连接（${data.latency}ms） · ${data.model}`;
            } else {
                statusEl.className = 'board-status offline';
                statusEl.textContent = '🔴 开发板离线';
            }
        } catch {
            statusEl.className = 'board-status offline';
            statusEl.textContent = '🔴 开发板离线';
        }
    }

    refresh();
    setInterval(refresh, 5000);
}
