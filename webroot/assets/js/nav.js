// Navigation des boutons (data-nav="back" | data-nav="<url ou #ancre>").
// Externalise les anciens onclick="..." pour rester compatible avec une CSP
// stricte (script-src 'self', sans unsafe-inline).
document.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-nav]');
    if (!btn) return;
    const target = btn.dataset.nav;
    if (target === 'back') {
        window.history.back();
    } else {
        window.location.href = target;
    }
});
