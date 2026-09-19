"""Arborescence de navigation du menu Guide (plan guide d'aide §3.6) -
miroir de la navigation reelle de l'application (OMEGA-SERV_PLAN-DETAILLE_
GUIDE_AIDE.md, Annexe A), independant du contenu (`registry.py`) :
une entree ici peut exister sans fiche ecrite (deploiement progressif,
`GuideMenuScreen` retombe sur un message "pas encore documente" dans ce
cas) - jamais l'inverse (`test_guide_registry.py` verifie qu'aucune
fiche ecrite ne reference un ecran absent de cet arbre)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuideMenuEntry:
    section: str
    screen_class_name: str
    title: str


GUIDE_MENU_ENTRIES: tuple[GuideMenuEntry, ...] = (
    GuideMenuEntry("Accueil", "HomeScreen", "Accueil"),
    GuideMenuEntry("Assistant premier lancement", "WizardWelcomeScreen", "1/8 - Bienvenue"),
    GuideMenuEntry("Assistant premier lancement", "WizardCapabilitiesScreen", "2/8 - Capacites"),
    GuideMenuEntry("Assistant premier lancement", "WizardProfileScreen", "3/8 - Profil"),
    GuideMenuEntry("Assistant premier lancement", "WizardBaseConfigScreen", "4/8 - Configuration de base"),
    GuideMenuEntry("Assistant premier lancement", "WizardTlsScreen", "5/8 - TLS"),
    GuideMenuEntry("Assistant premier lancement", "WizardCheckScreen", "6/8 - Verification"),
    GuideMenuEntry("Assistant premier lancement", "WizardSummaryScreen", "7/8 - Resume et ecriture"),
    GuideMenuEntry("Assistant premier lancement", "WizardServiceScreen", "8/8 - Service"),
    GuideMenuEntry("Registre des capacites", "CapabilitiesScreen", "Registre des capacites"),
    GuideMenuEntry("Registre des capacites", "CapabilityDetailScreen", "Detail d'une capacite"),
    GuideMenuEntry("Profils", "ProfilesScreen", "Profils"),
    GuideMenuEntry("Profils", "ApplyProfileScreen", "Appliquer un profil"),
    GuideMenuEntry("Configuration detaillee", "ServerConfigMenuScreen", "Configuration detaillee (menu)"),
    GuideMenuEntry("Configuration detaillee", "BaseConfigScreen", "Configuration de base"),
    GuideMenuEntry("Configuration detaillee", "LimitsScreen", "Resistance et limites"),
    GuideMenuEntry("Configuration detaillee", "SecurityScreen", "Securite generique"),
    GuideMenuEntry("Configuration detaillee", "AccessControlScreen", "Controle d'acces"),
    GuideMenuEntry("Configuration detaillee", "AliasesScreen", "Alias"),
    GuideMenuEntry("Configuration detaillee", "RedirectsScreen", "Redirections"),
    GuideMenuEntry("Configuration detaillee", "RewritesScreen", "Rewrites"),
    GuideMenuEntry("Configuration detaillee", "FastCgiScreen", "FastCGI / PHP-FPM"),
    GuideMenuEntry("Configuration detaillee", "DirlistingScreen", "Directory listing"),
    GuideMenuEntry("Configuration detaillee", "AuthMenuScreen", "Authentification"),
    GuideMenuEntry("Configuration detaillee", "CacheScreen", "Cache"),
    GuideMenuEntry("Configuration detaillee", "ErrorPagesScreen", "Pages d'erreur"),
    GuideMenuEntry("Configuration detaillee", "TrustedProxyScreen", "Proxies de confiance"),
    GuideMenuEntry("Configuration detaillee", "ReverseProxyScreen", "Reverse Proxy"),
    GuideMenuEntry("TLS", "TlsMenuScreen", "TLS (menu)"),
    GuideMenuEntry("TLS", "TlsStatusScreen", "Statut TLS"),
    GuideMenuEntry("TLS", "GenerateSelfSignedScreen", "Generer un certificat auto-signe"),
    GuideMenuEntry("TLS", "CaWizardScreen", "Assistant CA locale"),
    GuideMenuEntry("TLS", "LetsEncryptScreen", "Assistant Let's Encrypt (Certbot)"),
    GuideMenuEntry("TLS", "RenewalScheduleScreen", "Renouvellement automatique (Certbot)"),
    GuideMenuEntry("TLS", "RevokeCertificateScreen", "Revoquer un certificat"),
    GuideMenuEntry("TLS", "TlsToggleScreen", "Activer / desactiver TLS"),
    GuideMenuEntry("Gestion des logs", "LogsMenuScreen", "Gestion des logs (menu)"),
    GuideMenuEntry("Gestion des logs", "LogViewerScreen", "Voir / suivre un fichier log"),
    GuideMenuEntry("Gestion des logs", "LnavScreen", "Suivre les logs fusionnes (lnav)"),
    GuideMenuEntry("Gestion des logs", "LogRotationScreen", "Rotation / archivage des logs"),
    GuideMenuEntry("Gestion des logs", "RestoreLogArchiveScreen", "Restaurer une archive"),
    GuideMenuEntry("Gestion des logs", "PurgeLogArchivesScreen", "Purger des archives"),
    GuideMenuEntry("Gestion des logs", "ExportLogArchivesScreen", "Exporter des archives"),
    GuideMenuEntry("Gestion des logs", "LogStatsScreen", "Statistiques du log d'acces"),
    GuideMenuEntry("Gestion des logs", "TopIpsScreen", "Top IPs"),
    GuideMenuEntry("Service et instances", "ServiceScreen", "Service"),
    GuideMenuEntry("Service et instances", "InstancesScreen", "Multi-instance"),
    GuideMenuEntry("Service et instances", "OptionsScreen", "Options"),
    GuideMenuEntry("Service et instances", "ResourceStatusScreen", "Etat & Ressources"),
    GuideMenuEntry("Service et instances", "SimulateRequestScreen", "Simuler une requete"),
    GuideMenuEntry("Service et instances", "ConfigCheckScreen", "Verifier la configuration"),
    GuideMenuEntry("Audit et sauvegarde", "AuditScreen", "Audit de securite"),
    GuideMenuEntry("Audit et sauvegarde", "BackupScreen", "Sauvegarde de configuration"),
    GuideMenuEntry("Active Securite", "ActiveDefenseMenuScreen", "Active Securite (menu)"),
    GuideMenuEntry("Active Securite", "ActiveDefenseStatusScreen", "Active Defense - Statut"),
    GuideMenuEntry("Active Securite", "ActiveDefenseSettingsScreen", "Active Defense - Reglages"),
    GuideMenuEntry("Active Securite", "ThreatsScreen", "Active Defense - Menaces"),
    GuideMenuEntry("Active Securite", "IncidentsScreen", "Active Defense - Incidents"),
    GuideMenuEntry("Active Securite", "DeceptionScreen", "Active Defense - Leurres"),
    GuideMenuEntry("Active Securite", "ActiveDefenseSimulateScreen", "Active Defense - Simuler"),
    GuideMenuEntry("Active Securite", "WafStatusScreen", "WAF - Statut"),
    GuideMenuEntry("Active Securite", "WafModulesScreen", "WAF - Modules"),
    GuideMenuEntry("Active Securite", "WafTestScreen", "WAF - Tester une requete"),
    GuideMenuEntry("Active Securite", "WafCustomRuleScreen", "WAF - Regles personnalisees"),
    GuideMenuEntry("Active Securite", "WafCustomRuleWizardScreen", "WAF - Assistant regle personnalisee"),
    GuideMenuEntry("Active Securite", "WafRulePackPickerScreen", "WAF - Choix d'un pack de regles"),
    GuideMenuEntry("Reglages de l'application", "SettingsScreen", "Reglages de l'application"),
)
