import os

# === 🔑 Clés & Credentials ===
CHEMIN_CLE_JSON = os.environ.get("CHEMIN_CLE_JSON", "credentials.json")
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', 'VOTRE_TOKEN_PAR_DEFAUT')

# === 📊 Google Sheets - Fichiers ===
FICHIER_CLIENTS = "Suivi Programme et heure client"
FICHIER_PLANNING = "planning"
FICHIER_PROGRAMMES = "Méta-université_Programmes"

# === 📄 Google Sheets - Feuilles ===
FEUILLE_CLIENTS = "Clients"
FEUILLE_PLANNING = "Planning"
FEUILLE_REPONSES_SONDAGES = "Réponses Sondages"

# === ⏱️ Paramètres Planning ===
NB_JOURS_GENERATION = 2      # Nombre de jours de planning à générer
RETENTION_JOURS = 2           # Garde J-2 (purge plus vieux)
FUSEAU_HORAIRE = "Europe/Paris"
LANGUE = "fr_FR.UTF-8"

# Types par défaut pour les 3 slots horaires (Heure envoi 1/2/3)
# 1=Aphorisme, 2=Conseil, 3=Réflexion
DEFAULT_SLOT_TYPE_IDS = [1, 2, 3]

# === 📱 Paramètres Telegram ===
TELEGRAM_TIMEOUT = 10          # Timeout requêtes (secondes)
TELEGRAM_MAX_RETRIES = 3       # Nombre de tentatives en cas d'erreur
SEND_WINDOW_MINUTES = None     # Fenêtre d'envoi (None = pas de limite)

# === 📊 Paramètres Sondages ===
SONDAGE_ANONYME = True         # Les sondages sont anonymes
MESSAGE_COMMENTAIRE = "Pouvez-vous préciser ?"  # Message si "Autre :" cliqué

# === 📧 Paramètres Email (pour rapports) ===
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "")          # Votre email
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")  # Mot de passe ou app password

# === 🔧 Paramètres Techniques ===
GSHEETS_MAX_RETRIES = 5
GSHEETS_RETRY_BASE = 1.5     # Exponentiel (1.5^n) + jitter

# === 📓 Logger / Erreurs ===
ACTIVER_LOG = True
FICHIER_LOG = "journal_erreurs.log"