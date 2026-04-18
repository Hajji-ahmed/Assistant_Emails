// Toggle visibility for password fields on the config page.
document.addEventListener('click', (e) => {
    if (!e.target.classList.contains('toggle-secret')) return;
    const input = e.target.previousElementSibling;
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        e.target.textContent = 'Masquer';
    } else {
        input.type = 'password';
        e.target.textContent = 'Voir';
    }
});

// Flash messages: auto-dismiss after N ms (paused on hover), manual close on ×.
function initFlashes() {
    document.querySelectorAll('.flash[data-auto-dismiss]').forEach((el) => {
        const delay = parseInt(el.dataset.autoDismiss, 10) || 5000;
        let timer = null;

        const dismiss = () => {
            if (el.classList.contains('dismissing')) return;
            el.classList.add('dismissing');
            setTimeout(() => el.remove(), 300);
        };

        const start = () => { timer = setTimeout(dismiss, delay); };
        const pause = () => { clearTimeout(timer); };

        el.addEventListener('mouseenter', pause);
        el.addEventListener('mouseleave', start);
        el.querySelector('.flash-close')?.addEventListener('click', dismiss);

        start();
    });
}
document.addEventListener('DOMContentLoaded', initFlashes);
