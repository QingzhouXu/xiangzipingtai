document.addEventListener('DOMContentLoaded', function() {
    var merchantId = document.querySelector('[data-merchant-id]')?.dataset.merchantId;
    if (!merchantId || !document.getElementById('comments-list')) return;

    var currentRating = 5;
    var stars = document.querySelectorAll('#star-rating .star');
    var commentInput = document.getElementById('comment-input');
    var submitBtn = document.getElementById('submit-comment');
    var charCount = document.getElementById('char-count');

    // Star rating interaction
    if (stars.length > 0) {
        var starRatingContainer = document.getElementById('star-rating');
        stars.forEach(function(star) {
            star.addEventListener('click', function() {
                currentRating = parseInt(this.dataset.rating);
                updateStars(currentRating);
            });
            star.addEventListener('mouseenter', function() {
                updateStars(parseInt(this.dataset.rating));
            });
        });
        if (starRatingContainer) {
            starRatingContainer.addEventListener('mouseleave', function() {
                updateStars(currentRating);
            });
        }
        // 初始状态：默认5星全亮
        updateStars(currentRating);
    }

    function updateStars(rating) {
        stars.forEach(function(s) {
            s.classList.toggle('active', parseInt(s.dataset.rating) <= rating);
        });
    }

    // Character counter
    if (commentInput && charCount) {
        commentInput.addEventListener('input', function() {
            charCount.textContent = this.value.length + '/500';
        });
    }

    // Submit comment
    if (submitBtn) {
        submitBtn.addEventListener('click', function() {
            var content = (commentInput?.value || '').trim();
            if (!content) { alert('请输入评价内容'); return; }
            submitBtn.disabled = true;
            submitBtn.textContent = '提交中...';

            fetch('/api/merchant/comments', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ merchant_id: merchantId, content: content, rating: currentRating })
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    commentInput.value = '';
                    charCount.textContent = '0/500';
                    currentRating = 5;
                    updateStars(5);
                    loadComments();
                } else {
                    alert(data.error || '提交失败');
                }
            })
            .catch(function() { alert('网络错误，请重试'); })
            .finally(function() {
                submitBtn.disabled = false;
                submitBtn.textContent = '提交评价';
            });
        });
    }

    function loadComments() {
        fetch('/api/merchant/comments?merchant_id=' + encodeURIComponent(merchantId))
            .then(function(r) { return r.json(); })
            .then(function(data) {
                renderComments(data.comments || []);
            })
            .catch(function() {
                document.getElementById('comments-list').innerHTML = '<div class="comments-error">加载评论失败</div>';
            });
    }

    function renderComments(comments) {
        var list = document.getElementById('comments-list');
        var count = document.getElementById('comments-count');
        if (count) count.textContent = comments.length + ' 条评价';

        if (comments.length === 0) {
            list.innerHTML = '<div class="comments-empty">暂无评价，成为第一个评价的用户吧！</div>';
            return;
        }

        list.innerHTML = comments.map(function(c) {
            var starsHtml = '';
            for (var i = 1; i <= 5; i++) {
                starsHtml += '<span class="comment-star' + (i <= c.rating ? ' filled' : '') + '"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="' + (i <= c.rating ? '#f59e0b' : 'none') + '" stroke="' + (i <= c.rating ? '#f59e0b' : 'currentColor') + '" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></span>';
            }
            var date = new Date(c.timestamp);
            return '<div class="comment-item">' +
                '<div class="comment-avatar-small">' + escapeHtml((c.display_name || c.username || '?')[0]) + '</div>' +
                '<div class="comment-body">' +
                    '<div class="comment-author">' + escapeHtml(c.display_name || c.username) +
                        '<span class="comment-rating-stars">' + starsHtml + '</span>' +
                    '</div>' +
                    '<div class="comment-text">' + escapeHtml(c.content) + '</div>' +
                    '<div class="comment-time">' + date.toLocaleDateString() + '</div>' +
                '</div>' +
            '</div>';
        }).join('');
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initial load
    loadComments();
});
