/* Theme du panneau pour CE navigateur (plan tableau de bord web §9.7, decision de l'auteur du 2026-11-17) : gardé
   dans un cookie de ce navigateur, jamais écrit sur le serveur ; « Thème de l'instance » le retire. */
"use strict";

(function () {
  const select = document.getElementById("theme-select");
  if (!select) return;
  select.addEventListener("change", () => {
    const secure = location.protocol === "https:" ? "; Secure" : "";
    const value = select.value;
    document.cookie = "omega_admin_theme=" + encodeURIComponent(value) + "; Path=/; SameSite=Strict" + secure +
      (value ? "; Max-Age=31536000" : "; Max-Age=0");
    location.reload();
  });
})();
