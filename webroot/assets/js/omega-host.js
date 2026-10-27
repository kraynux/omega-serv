/* Omega-Serv - nom du serveur reellement visite dans l'en-tete des pages et des listings.
   Fichier separe dans /assets/ (jamais un script dans la page) : la CSP stricte d'omega-serv
   (script-src 'self') bloque tout script inline. Sans JavaScript, le texte de repli
   « Omega-server » reste affiche. */
(function () {
    var host = location.hostname || "Omega-Server";
    var short = "\u2014 " + host.split(".")[0];
    function set(selector, text) {
        var nodes = document.querySelectorAll(selector);
        for (var i = 0; i < nodes.length; i++) { nodes[i].textContent = text; }
    }
    function apply() {
        set("#omega-host, .omega-header__host, #omega-header-host", host);
        set(".omega-header__subtitle, #omega-header-subtitle", short);
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", apply);
    } else {
        apply();
    }
})();
