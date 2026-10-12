// Boutons "Copier" des blocs de code (.copy-btn), par délégation d'événement.
// Externalise l'ancien onclick="copyCode(this)" pour rester compatible avec
// une CSP stricte (script-src 'self', sans unsafe-inline).
document.addEventListener('click', (event) => {
    const btn = event.target.closest('.copy-btn');
    if (!btn) return;

    const pre = btn.closest('.code-block-wrapper')?.querySelector('pre');
    const code = pre ? pre.innerText : '';
    const restoreLabel = () => {
        const original = btn.textContent;
        btn.textContent = '✓ Copié !';
        setTimeout(() => { btn.textContent = original; }, 2000);
    };

    navigator.clipboard.writeText(code).then(restoreLabel).catch(() => {
        if (!pre) return;
        const range = document.createRange();
        range.selectNode(pre);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        document.execCommand('copy');
        window.getSelection().removeAllRanges();
        restoreLabel();
    });
});
