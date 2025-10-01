# MetaBot – Assistant d'envoi Telegram automatique


## 1. Description du projet

**MetaBot** est un assistants pour automatisé qui gère la planification et l’envoi de messages dans différents canaux Telegram, à partir d’un programme défini dans Google Sheets.  
**Hébergement :** GitHub Actions (cron), déploiement facile sur d’autres plateformes cloud.

---

## 2. Fonctionnalités principales

- Génération automatique d’un planning d’envoi à partir de fichiers clients & programmes Google Sheets.
- Envoi des messages Telegram dans les bons canaux à l’heure prévue.
- Scripts autonomes et reconfigurables (pas besoin de coder pour changer les réglages).
- Automatisation complète (cron GitHub Actions, logs…).
- Sécurité via gestion des secrets GitHub.

---

## 3. Structure des fichiers

| Fichier                            | Rôle                                                                                        |
|-------------------------------------|---------------------------------------------------------------------------------------------|
| `Script_Planning.py`                | Génère le planning d’envoi à partir des fichiers clients & programmes Google Sheets          |
| `Script_Bot.py`                     | Envoie les messages Telegram planifiés                                                      |
| `config.py`                         | Paramétrage centralisé : tokens, noms des fichiers, noms des feuilles, paramètres horaires… |
| `requirements.txt`                  | Liste des dépendances Python à installer                                                    |
| `.github/workflows/bot.yaml`        | Cron pour automatiser l’envoi régulier via GitHub Actions                                   |
| `.github/workflows/planning.yaml`   | Cron pour la génération quotidienne du planning                                             |
| `README.md`                         | Ce fichier                                                                                  |
| `google_service_account.json`       | Clé API Google pour accès aux fichiers Sheets (à placer dans les secrets, jamais en clair)  |

---

## 4. Explication des scripts

- **Script_Planning.py**  
  Génère chaque jour un planning complet à partir des données client et programme.
  - Associe chaque client à son programme
  - Remplit une feuille “planning” avec : client, programme, date, heure, type de message, canal, message, envoyé/non

- **Script_Bot.py**  
  Exécute l’envoi des messages prévus pour chaque créneau (heure/date), met à jour la colonne “envoyé”.

- **config.py**  
  Centralise tous les paramètres modifiables :  
  (tokens Telegram, noms des fichiers Google Sheets, noms des feuilles, timezone, etc.)

- **requirements.txt**  
  Liste toutes les bibliothèques Python nécessaires :  
  (pandas, gspread, google-auth, requests, pytz…)

---

## 5. Organisation des fichiers Google Sheets

### Trois fichiers principaux :

#### Fichier Clients (`FICHIER_CLIENTS`)

- **Feuille :** Clients
- **Colonnes principales :**
  - `nom_client`
  - `programme`
  - `date_demarrage`
  - `chat_id`
  - `heure_conseil`
  - `heure_aphorisme`
  - `heure_reflexion`
  - `saison`
  - ...

#### Fichier Programmes (`FICHIER_PROGRAMMES`)

- **Plusieurs feuilles** (une par numéro de programme, ex : `002`, `010`…)
- **Colonnes :**
  - `jour`
  - `type` (ex : 1-Conseil matin, etc.)
  - `message`
  - `saison`
  - ...

#### Fichier Planning (`FICHIER_PLANNING`)

- **Feuille :** Planning
- **Colonnes générées :**
  - `nom_client`
  - `programme`
  - `date`
  - `heure`
  - `type`
  - `chat_id`
  - `message`
  - `envoye`

---

## 6. Automatisation via GitHub Actions (Cron)

- `bot.yaml` : Exécute `Script_Bot.py` toutes les heures (`cron 0 * * * *`)
- `planning.yaml` : Exécute `Script_Planning.py` chaque jour (`cron 0 2 * * *`)

> Les logs d’exécution sont visibles dans l’onglet **Actions** du repo GitHub.

---

## 7. Gestion des secrets GitHub Actions

- Onglet : `Settings > Secrets and variables > Actions`
- **Secrets obligatoires :**
    - `TELEGRAM_TOKEN` : Token du bot Telegram (pas de guillemets)
    - `GOOGLE_CREDENTIALS_B64` : Fichier credentials Google, encodé en base64
    - Autres secrets selon besoin (noms de fichiers/feuilles si personnalisés)
- **Règle :** Jamais de clé ou token en dur dans le code ou sur le repo !

---

## 8. Procédure de modification et maintenance

- **Pour modifier :**
    - Un paramètre : éditer `config.py` ou le secret concerné
    - Un script : modifier le `.py`, commit, et push (l’Action se relance automatiquement)

- **Pour voir les logs/débug :**
    - GitHub : onglet Actions > sélectionner le workflow et le run
    - Google Sheets : vérifier les colonnes du planning

- **Pour relancer manuellement :** cliquer sur “Run workflow” dans Actions

---

## 9. FAQ et points de vigilance

**Pourquoi un message n’est pas envoyé ?**  
→ Vérifier le format de la date et heure, la colonne `envoye`, le `chat_id`, le token…

**Les secrets ne sont pas pris en compte ?**  
→ Vérifier que les noms sont exacts (pas de guillemets), voir les logs

**Je veux changer de canal Telegram ?**  
→ Modifier la colonne `chat_id` dans le fichier clients ou planning

**Je veux changer la fréquence d’envoi ?**  
→ Modifier le cron dans `.github/workflows/*.yaml`

---

## 10. Contact & support

Pour toute question ou assistance :

- Contacter le responsable du projet (`aubinherault64@gmail.com`)

> Projet conçu pour être **maintenable**, **sécurisé**, et **adaptable** sans compétences techniques avancées.
