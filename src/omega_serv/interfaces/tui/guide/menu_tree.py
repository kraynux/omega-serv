"""Arborescence de navigation du menu Guide (plan guide d'aide §3.6) -
miroir de la navigation reelle de l'application (OMEGA-SERV_PLAN-DETAILLE_
GUIDE_AIDE.md, Annexe A), independant du contenu (`registry.py`) :
une entree ici peut exister sans fiche ecrite (deploiement progressif,
`GuideMenuScreen` retombe sur un message "pas encore documente" dans ce
cas) - jamais l'inverse (`test_guide_registry.py` verifie qu'aucune
fiche ecrite ne reference un ecran absent de cet arbre)."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.core.i18n import _


@dataclass(frozen=True)
class GuideMenuEntry:
    section: str
    screen_class_name: str
    title: str


GUIDE_MENU_ENTRIES: tuple[GuideMenuEntry, ...] = (
    GuideMenuEntry(_("Accueil"), "HomeScreen", _("Accueil")),
    GuideMenuEntry(_("Assistant premier lancement"), "WizardWelcomeScreen", _("1/8 - Bienvenue")),
    GuideMenuEntry(_("Assistant premier lancement"), "WizardCapabilitiesScreen", _("2/8 - Capacités")),
    GuideMenuEntry(_("Assistant premier lancement"), "WizardProfileScreen", _("3/8 - Profil")),
    GuideMenuEntry(_("Assistant premier lancement"), "WizardBaseConfigScreen", _("4/8 - Configuration de base")),
    GuideMenuEntry(_("Assistant premier lancement"), "WizardTlsScreen", _("5/8 - TLS")),
    GuideMenuEntry(_("Assistant premier lancement"), "WizardCheckScreen", _("6/8 - Vérification")),
    GuideMenuEntry(_("Assistant premier lancement"), "WizardSummaryScreen", _("7/8 - Résumé et écriture")),
    GuideMenuEntry(_("Assistant premier lancement"), "WizardServiceScreen", _("8/8 - Service")),
    GuideMenuEntry(_("Registre des capacités"), "CapabilitiesScreen", _("Registre des capacités")),
    GuideMenuEntry(_("Registre des capacités"), "CapabilityDetailScreen", _("Détail d'une capacité")),
    GuideMenuEntry(_("Profils"), "ProfilesScreen", _("Profils")),
    GuideMenuEntry(_("Profils"), "ApplyProfileScreen", _("Appliquer un profil")),
    GuideMenuEntry(_("Configuration détaillée"), "ServerConfigMenuScreen", _("Configuration détaillée (menu)")),
    GuideMenuEntry(_("Configuration détaillée"), "BaseConfigScreen", _("Configuration de base")),
    GuideMenuEntry(_("Configuration détaillée"), "LimitsScreen", _("Résistance et limites")),
    GuideMenuEntry(_("Configuration détaillée"), "SecurityScreen", _("Sécurité générique")),
    GuideMenuEntry(_("Configuration détaillée"), "CspZoneWizardScreen", _("Sécurité générique - Assistant zone CSP")),
    GuideMenuEntry(_("Configuration détaillée"), "AccessControlScreen", _("Contrôle d'accès")),
    GuideMenuEntry(_("Configuration détaillée"), "AliasesScreen", _("Alias")),
    GuideMenuEntry(_("Configuration détaillée"), "RedirectsScreen", _("Redirections")),
    GuideMenuEntry(_("Configuration détaillée"), "RewritesScreen", _("Rewrites")),
    GuideMenuEntry(_("Configuration détaillée"), "FastCgiScreen", _("FastCGI / PHP-FPM")),
    GuideMenuEntry(_("Configuration détaillée"), "DirlistingScreen", _("Directory listing")),
    GuideMenuEntry(_("Configuration détaillée"), "AuthMenuScreen", _("Authentification")),
    GuideMenuEntry(_("Configuration détaillée"), "CacheScreen", _("Cache")),
    GuideMenuEntry(_("Configuration détaillée"), "ErrorPagesScreen", _("Pages d'erreur")),
    GuideMenuEntry(_("Configuration détaillée"), "TrustedProxyScreen", _("Proxies de confiance")),
    GuideMenuEntry(_("Configuration détaillée"), "ReverseProxyScreen", _("Reverse Proxy")),
    GuideMenuEntry(_("Configuration détaillée"), "ReverseProxyUpstreamStatusScreen", _("État en direct des backends")),
    GuideMenuEntry(_("Configuration détaillée"), "ReverseProxyCacheScreen", _("Cache du reverse proxy")),
    GuideMenuEntry(_("TLS"), "TlsMenuScreen", _("TLS (menu)")),
    GuideMenuEntry(_("TLS"), "TlsStatusScreen", _("Statut TLS")),
    GuideMenuEntry(_("TLS"), "GenerateSelfSignedScreen", _("Générer un certificat auto-signé")),
    GuideMenuEntry(_("TLS"), "CaWizardScreen", _("Assistant CA locale")),
    GuideMenuEntry(_("TLS"), "LetsEncryptScreen", _("Assistant Let's Encrypt (Certbot)")),
    GuideMenuEntry(_("TLS"), "RenewalScheduleScreen", _("Renouvellement automatique (Certbot)")),
    GuideMenuEntry(_("TLS"), "RevokeCertificateScreen", _("Révoquer un certificat")),
    GuideMenuEntry(_("TLS"), "TlsToggleScreen", _("Activer / désactiver TLS")),
    GuideMenuEntry(_("Gestion des logs"), "LogsMenuScreen", _("Gestion des logs (menu)")),
    GuideMenuEntry(_("Gestion des logs"), "LogLibraryScreen", _("Bibliothèque")),
    GuideMenuEntry(_("Gestion des logs"), "RemoteLogSourcesScreen", _("Sources distantes (SSH)")),
    GuideMenuEntry(_("Gestion des logs"), "LogFavoritesScreen", _("Favoris")),
    GuideMenuEntry(_("Gestion des logs"), "LogViewScreen", _("Voir les logs")),
    GuideMenuEntry(_("Gestion des logs"), "LogSimpleViewerScreen", _("Voir les logs - Simple")),
    GuideMenuEntry(_("Gestion des logs"), "LogViewerScreen", _("Voir les logs - Classique")),
    GuideMenuEntry(_("Gestion des logs"), "LnavScreen", _("Suivre les logs fusionnés (lnav)")),
    GuideMenuEntry(_("Gestion des logs"), "ProcessIpScreen", _("Voir et traiter IP")),
    GuideMenuEntry(_("Gestion des logs"), "LogRotationScreen", _("Rotation / archivage des logs")),
    GuideMenuEntry(_("Gestion des logs"), "RestoreLogArchiveScreen", _("Restaurer une archive")),
    GuideMenuEntry(_("Gestion des logs"), "PurgeLogArchivesScreen", _("Purger des archives")),
    GuideMenuEntry(_("Gestion des logs"), "ExportLogArchivesScreen", _("Exporter des archives")),
    GuideMenuEntry(_("Service et instances"), "ServiceScreen", _("Service")),
    GuideMenuEntry(_("Service et instances"), "InstancesScreen", _("Multi-instance")),
    GuideMenuEntry(_("Service et instances"), "OptionsScreen", _("Options")),
    GuideMenuEntry(_("Service et instances"), "ResourceStatusScreen", _("État & Ressources")),
    GuideMenuEntry(_("Service et instances"), "SimulateRequestScreen", _("Simuler une requête")),
    GuideMenuEntry(_("Service et instances"), "ConfigCheckScreen", _("Vérifier la configuration")),
    GuideMenuEntry(_("Audit et sauvegarde"), "AuditScreen", _("Audit de sécurité")),
    GuideMenuEntry(_("Audit et sauvegarde"), "BackupScreen", _("Sauvegarde de configuration")),
    GuideMenuEntry(_("Active Sécurité"), "ActiveDefenseMenuScreen", _("Active Sécurité (menu)")),
    GuideMenuEntry(_("Active Sécurité"), "ActiveDefenseStatusScreen", _("Active Defense - Statut")),
    GuideMenuEntry(_("Active Sécurité"), "ActiveDefenseSettingsScreen", _("Active Defense - Réglages")),
    GuideMenuEntry(_("Active Sécurité"), "ThreatsScreen", _("Active Defense - Menaces")),
    GuideMenuEntry(_("Active Sécurité"), "IncidentsScreen", _("Active Defense - Incidents")),
    GuideMenuEntry(_("Active Sécurité"), "DeceptionScreen", _("Active Defense - Leurres")),
    GuideMenuEntry(_("Active Sécurité"), "ActiveDefenseSimulateScreen", _("Active Defense - Simuler")),
    GuideMenuEntry(_("Active Sécurité"), "WafStatusScreen", _("WAF - Statut")),
    GuideMenuEntry(_("Active Sécurité"), "WafModulesScreen", _("WAF - Modules")),
    GuideMenuEntry(_("Active Sécurité"), "WafRateLimitScreen", _("WAF - Exclusions et débit")),
    GuideMenuEntry(_("Active Sécurité"), "WafTestScreen", _("WAF - Tester une requête")),
    GuideMenuEntry(_("Active Sécurité"), "WafCustomRuleScreen", _("WAF - Règles et listes personnalisées")),
    GuideMenuEntry(_("Active Sécurité"), "WafCustomRuleWizardScreen", _("WAF - Assistant règle / chargement de liste")),
    GuideMenuEntry(_("Active Sécurité"), "PathListEditorScreen", _("WAF - Éditeur de liste")),
    GuideMenuEntry(_("Active Sécurité"), "KeywordListSettingsScreen", _("WAF - Modifier une liste")),
    GuideMenuEntry(_("Active Sécurité"), "WafRulePackPickerScreen", _("WAF - Choix d'un pack de règles")),
    GuideMenuEntry(_("Active Sécurité"), "WafMagnetScreen", _("WAF - Magnet (import d'un WAF externe)")),
    GuideMenuEntry(_("Réglages de l'application"), "SettingsScreen", _("Réglages de l'application")),
)
