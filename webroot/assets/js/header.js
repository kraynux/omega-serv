(function () {
  function fixParent() {
    var link = document.getElementById('omega-parent-link');
    if (!link) return;

    // Priorité : lien généré par le serveur
    var serverLink = document.querySelector('.omega-parent a[href]');
    if (serverLink) {
      link.href = serverLink.getAttribute('href');
      return;
    }

    // Fallback : calcul depuis l'URL
    var parts = location.pathname.replace(/\/+$/, '').split('/').filter(Boolean);
    parts.pop();
    link.href = '/' + parts.join('/') + (parts.length ? '/' : '');
  }

  fixParent();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fixParent);
  }
})();
