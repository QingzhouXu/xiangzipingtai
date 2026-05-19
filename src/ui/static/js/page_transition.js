(function() {
    if (window.__pageTransitionInstalled) return;
    window.__pageTransitionInstalled = true;

    var hiding = false;

    document.addEventListener('click', function(e) {
        if (hiding) return;
        var link = e.target.closest('a');
        if (!link) return;
        var href = link.getAttribute('href');
        if (!href) return;
        if (href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
        if (link.getAttribute('target') === '_blank') return;
        if (link.getAttribute('download') !== null) return;

        var linkUrl;
        try {
            linkUrl = new URL(href, window.location.origin);
        } catch (_) {
            return;
        }
        if (linkUrl.origin !== window.location.origin) return;

        if (linkUrl.pathname === window.location.pathname && linkUrl.search === window.location.search) return;

        e.preventDefault();
        hiding = true;

        document.body.classList.add('is-exiting');

        setTimeout(function() {
            window.location.href = linkUrl.href;
        }, 420);
    });

    if (document.documentElement.classList.contains('page-entering')) {
        requestAnimationFrame(function() {
            document.documentElement.classList.remove('page-entering');
            hiding = false;
        });
    } else {
        hiding = false;
    }

    var themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            var isDark = document.documentElement.classList.contains('dark');
            var nextTheme = isDark ? 'light' : 'dark';

            document.documentElement.style.transition = 'all 800ms ease';

            if (isDark) {
                document.documentElement.classList.remove('dark');
            } else {
                document.documentElement.classList.add('dark');
            }
            localStorage.setItem('theme', nextTheme);

            setTimeout(function() {
                document.documentElement.style.transition = '';
            }, 800);
        });
    }
})();