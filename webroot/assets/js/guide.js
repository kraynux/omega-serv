// Comportements propres a guide.html : tout deplier/replier les sections
// wiki, et auto-ouverture des sections ancetres lors d'une navigation par
// ancre (#id). Externalise pour rester compatible avec une CSP stricte
// (script-src 'self', sans unsafe-inline) : voir aussi nav.js et
// copy-code.js, charges avant celui-ci.

document.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-toggle-all]');
    if (!btn) return;
    const open = btn.dataset.toggleAll === 'open';
    document.querySelectorAll('.wiki-section').forEach(el => el.open = open);
    document.querySelectorAll('.sub-section').forEach(el => el.open = open);
    document.querySelectorAll('.screen-card').forEach(el => el.open = open);
    document.querySelectorAll('.faq-item').forEach(el => el.open = open);
});

document.addEventListener('DOMContentLoaded', () => {
    function openAllAncestors() {
        const hash = window.location.hash;
        if (!hash) return;
        const target = document.querySelector(hash);
        if (!target) return;
        let el = target;
        while (el) {
            if (el.tagName === 'DETAILS') el.open = true;
            el = el.parentElement;
        }
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    openAllAncestors();
    window.addEventListener('hashchange', openAllAncestors);
});
