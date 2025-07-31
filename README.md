# MetaBot – Assistant d'envoi Telegram automatique

## Sommaire

1. [Description du projet](#description-du-projet)
2. [Fonctionnalités principales](#fonctionnalités-principales)
3. [Structure des fichiers](#structure-des-fichiers)
4. [Explication des scripts](#explication-des-scripts)
5. [Configuration (`config.py` et `requirements.txt`)](#configuration-configpy-et-requirementstxt)
6. [Organisation des fichiers Google Sheets](#organisation-des-fichiers-google-sheets)
7. [Dossier template Google Sheets](#dossier-template-google-sheets)
8. [Automatisation via GitHub Actions (Cron)](#automatisation-via-github-actions-cron)
9. [Logs, erreurs, et debug](#logs-erreurs-et-debug)
10. [Gestion des secrets GitHub Actions](#gestion-des-secrets-github-actions)
11. [Procédure de modification et maintenance](#procédure-de-modification-et-maintenance)
12. [FAQ et points de vigilance](#faq-et-points-de-vigilance)
13. [Améliorations prévues](#améliorations-prévues)
14. [Contact & support](#contact--support)

---

## 1. Description du projet

**MetaBot** est un assistant automatisé qui gère la planification et l’envoi de messages dans différents canaux Telegram, à partir d’un programme défini dans Google Sheets.  
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
| `template/`                         | Modèles de fichiers Google Sheets pour faciliter la configuration initiale                  |
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

## 5. Configuration (`config.py` et `requirements.txt`)

- **`config.py`** :  
  À renseigner :
  - Le nom exact des fichiers Google Sheets
  - Le nom des feuilles utilisées (Clients, Planning, etc.)
  - Le token Telegram (injecté depuis les secrets GitHub Actions)
  - Le chemin vers le credentials Google (généralement `credentials.json`, injecté depuis les secrets GitHub)
  - Les paramètres horaires si besoin

- **`requirements.txt`** :  
  À installer via :
  ```bash
  pip install -r requirements.txt

## 6. Organisation des fichiers Google Sheets

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

> Un dossier `/template` contient des exemples de chaque fichier avec les bonnes colonnes pour démarrer facilement.

---

## 7. Dossier template Google Sheets

- Contient des modèles pré-remplis pour chaque type de fichier nécessaire
- À dupliquer directement sur Google Drive pour initialiser une nouvelle instance du bot

---

## 8. Automatisation via GitHub Actions (Cron)

- `bot.yaml` : Exécute `Script_Bot.py` toutes les heures (`cron 0 * * * *`)
- `planning.yaml` : Exécute `Script_Planning.py` chaque jour (`cron 0 2 * * *`)

> Les logs d’exécution sont visibles dans l’onglet **Actions** du repo GitHub.

---

## 9. Logs, erreurs, et debug

- Les erreurs sont loggées automatiquement (fichier `journal_erreurs.log` si activé dans `config.py`)
- Pour debug :
    - Regarder les logs des Actions GitHub (historique complet, erreurs Python, outputs `print`)
    - Vérifier les valeurs dans Google Sheets (notamment la colonne `envoye`)
    - Ajouter des prints ou logs supplémentaires en cas de besoin

---

## 10. Gestion des secrets GitHub Actions

- Onglet : `Settings > Secrets and variables > Actions`
- **Secrets obligatoires :**
    - `TELEGRAM_TOKEN` : Token du bot Telegram (pas de guillemets)
    - `GOOGLE_CREDENTIALS_B64` : Fichier credentials Google, encodé en base64
    - Autres secrets selon besoin (noms de fichiers/feuilles si personnalisés)
- **Règle :** Jamais de clé ou token en dur dans le code ou sur le repo !

---

## 11. Procédure de modification et maintenance

- **Pour modifier :**
    - Un paramètre : éditer `config.py` ou le secret concerné
    - Un script : modifier le `.py`, commit, et push (l’Action se relance automatiquement)
    - Un template Google Sheet : remplacer le modèle dans `/template`

- **Pour voir les logs/débug :**
    - GitHub : onglet Actions > sélectionner le workflow et le run
    - Google Sheets : vérifier les colonnes du planning

- **Pour relancer manuellement :** cliquer sur “Run workflow” dans Actions

---

## 12. FAQ et points de vigilance

**Pourquoi un message n’est pas envoyé ?**  
→ Vérifier le format de la date et heure, la colonne `envoye`, le `chat_id`, le token…

**Les secrets ne sont pas pris en compte ?**  
→ Vérifier que les noms sont exacts (pas de guillemets), voir les logs

**Je veux changer de canal Telegram ?**  
→ Modifier la colonne `chat_id` dans le fichier clients ou planning

**Je veux changer la fréquence d’envoi ?**  
→ Modifier le cron dans `.github/workflows/*.yaml`

---

## 13. Améliorations prévues

| Tâche                                 | Statut     |
| ------------------------------------- | ---------- |
| Fichier de logs détaillés             | En cours   |
| Rapport quotidien sur Telegram admin  | À venir    |
| Interface de paramétrage simplifiée   | À discuter |
| Notifications en cas d’échec d’envoi  | À venir    |
| Gestion multi-projet / multi-instance | À discuter |

---

## 14. Contact & support

Pour toute question ou assistance :

- Contacter le responsable du projet (`ton_mail@exemple.com` ou Telegram)
- Ou créer une “Issue” sur le repo GitHub

> Projet conçu pour être **maintenable**, **sécurisé**, et **adaptable** sans compétences techniques avancées.
