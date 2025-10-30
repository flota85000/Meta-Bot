# MetaBot – Assistant d'envoi Telegram automatique


## 1. Description du projet

**MetaBot** est un assistant automatisé qui gère la planification et l'envoi de messages dans différents canaux Telegram, à partir d'un programme défini dans Google Sheets.  
**Hébergement :** GitHub Actions (cron), déploiement facile sur d'autres plateformes cloud.

---

## 2. Fonctionnalités principales

- Génération automatique d'un planning d'envoi à partir de fichiers clients & programmes Google Sheets.
- Envoi de **messages texte**, **images** et **sondages** Telegram dans les bons canaux à l'heure prévue.
- Collecte automatique des réponses aux sondages dans une feuille Google Sheets dédiée.
- Scripts autonomes et reconfigurables (pas besoin de coder pour changer les réglages).
- Automatisation complète (cron GitHub Actions, logs…).
- Sécurité via gestion des secrets GitHub.

---

## 3. Structure des fichiers

| Fichier                            | Rôle                                                                                        |
|-------------------------------------|---------------------------------------------------------------------------------------------|
| `Script_Planning.py`                | Génère le planning d'envoi à partir des fichiers clients & programmes Google Sheets          |
| `Script_Bot.py`                     | Envoie les messages Telegram planifiés (texte, images, sondages) et collecte les réponses    |
| `config.py`                         | Paramétrage centralisé : tokens, noms des fichiers, noms des feuilles, paramètres horaires… |
| `requirements.txt`                  | Liste des dépendances Python à installer                                                    |
| `.github/workflows/bot.yaml`        | Cron pour automatiser l'envoi régulier via GitHub Actions                                   |
| `.github/workflows/planning.yaml`   | Cron pour la génération quotidienne du planning                                             |
| `README.md`                         | Ce fichier                                                                                  |
| `google_service_account.json`       | Clé API Google pour accès aux fichiers Sheets (à placer dans les secrets, jamais en clair)  |

---

## 4. Explication des scripts

- **Script_Planning.py**  
  Génère chaque jour un planning complet à partir des données client et programme.
  - Associe chaque client à son programme
  - Remplit une feuille "planning" avec : client, programme, date, heure, type de message, canal, message, format, envoyé/non

- **Script_Bot.py**  
  Exécute l'envoi des messages prévus pour chaque créneau (heure/date), met à jour la colonne "envoyé".
  - Supporte 3 formats : **texte**, **image**, **sondage**
  - Collecte automatiquement les réponses aux sondages via l'API Telegram
  - Enregistre les réponses dans la feuille "Réponses Sondages"

- **config.py**  
  Centralise tous les paramètres modifiables :  
  (tokens Telegram, noms des fichiers Google Sheets, noms des feuilles, timezone, etc.)

- **requirements.txt**  
  Liste toutes les bibliothèques Python nécessaires :  
  (pandas, gspread, google-auth, requests, pytz…)

---

## 5. Organisation des fichiers Google Sheets

### Quatre fichiers/feuilles principaux :

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
  - `format` (**texte**, **image**, **sondage**)
  - `saison`
  - `url` (optionnel, pour les images)
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
  - `format`
  - `url`
  - `envoye`

#### Feuille Réponses Sondages (`FEUILLE_REPONSES_SONDAGES`)

- **Créée automatiquement** par le bot si elle n'existe pas
- **Colonnes :**
  - `User ID` : ID Telegram de l'utilisateur
  - `Prénom` : Prénom de l'utilisateur
  - `Nom` : Nom de famille
  - `Username` : @username Telegram
  - `Date et Heure` : Timestamp de la réponse
  - `Question` : Question du sondage (ou ID du poll)
  - `Réponse(s)` : Réponse(s) choisie(s)

---

## 6. 📊 Nouveau : Fonctionnalité Sondages

### Comment créer un sondage

Dans votre fichier **Programmes**, utilisez la colonne `format` avec la valeur **"sondage"**.

Le contenu du champ `message` doit suivre ce format :

```
Question du sondage ?
Option 1
Option 2
Option 3
Option 4
```

**Règles :**
- **Ligne 1** = La question
- **Lignes suivantes** = Les options de réponse (minimum 2, maximum 10)
- Chaque option doit être sur une ligne séparée

### Exemple de contenu

```
Quel est votre plat préféré ?
Pizza
Pasta
Sushi
Burger
Salade
```

### Configuration des sondages

Dans `config.py`, vous pouvez configurer :

```python
SONDAGE_ANONYME = True           # Les votes sont-ils anonymes ?
SONDAGE_MULTI_REPONSES = False   # Permettre plusieurs réponses ?
```

### Collecte des réponses

Les réponses sont automatiquement collectées à chaque exécution du bot et enregistrées dans la feuille **"Réponses Sondages"** avec :
- Les informations de l'utilisateur (prénom, nom, username)
- La date et l'heure de la réponse
- La question posée
- La ou les réponse(s) choisie(s)

---

## 7. Automatisation via GitHub Actions (Cron)

- `bot.yaml` : Exécute `Script_Bot.py` toutes les heures (`cron 1 * * * *`)
  - Envoie les messages planifiés
  - Collecte les réponses aux sondages
- `planning.yaml` : Exécute `Script_Planning.py` chaque jour (`cron 0 7 * * *`)

> Les logs d'exécution sont visibles dans l'onglet **Actions** du repo GitHub.

---

## 8. Gestion des secrets GitHub Actions

- Onglet : `Settings > Secrets and variables > Actions`
- **Secrets obligatoires :**
    - `TELEGRAM_TOKEN` : Token du bot Telegram (pas de guillemets)
    - `GOOGLE_CREDENTIALS_B64` : Fichier credentials Google, encodé en base64
    - Autres secrets selon besoin (noms de fichiers/feuilles si personnalisés)
- **Règle :** Jamais de clé ou token en dur dans le code ou sur le repo !

---

## 9. Procédure de modification et maintenance

### Pour modifier un paramètre :
- Éditer `config.py` ou le secret concerné
- Pour changer le format (texte/image/sondage) : modifier la colonne `Format` dans le fichier Programmes

### Pour créer un nouveau sondage :
1. Dans votre fichier **Programmes**, ajoutez une ligne avec `Format = "sondage"`
2. Dans la colonne `Phrase/Message`, écrivez votre question et vos options (une par ligne)
3. Le planning sera généré automatiquement

### Pour voir les logs/débug :
- GitHub : onglet Actions > sélectionner le workflow et le run
- Google Sheets : vérifier les colonnes du planning et la feuille "Réponses Sondages"

### Pour relancer manuellement :
- Cliquer sur "Run workflow" dans Actions

---

## 10. FAQ et points de vigilance

**Pourquoi un sondage n'est pas envoyé ?**  
→ Vérifier que le format est bien "sondage", que le message contient au moins une question et 2 options (max 10), que le format est correct (une ligne par option)

**Les réponses aux sondages ne s'enregistrent pas ?**  
→ Vérifier que la feuille "Réponses Sondages" existe (elle est créée automatiquement au premier lancement)  
→ Vérifier les logs dans GitHub Actions pour voir si des erreurs sont survenues

**Je ne vois pas les réponses détaillées (texte des options) ?**  
→ Par limitation de l'API Telegram en mode getUpdates, seuls les indices des options sont disponibles. Pour une solution complète, il faudrait implémenter un webhook Telegram.

**Pourquoi un message n'est pas envoyé ?**  
→ Vérifier le format de la date et heure, la colonne `envoye`, le `chat_id`, le token…

**Les secrets ne sont pas pris en compte ?**  
→ Vérifier que les noms sont exacts (pas de guillemets), voir les logs

**Je veux changer de canal Telegram ?**  
→ Modifier la colonne `chat_id` dans le fichier clients ou planning

**Je veux changer la fréquence d'envoi ?**  
→ Modifier le cron dans `.github/workflows/*.yaml`

**Comment savoir si un sondage a été bien formaté ?**  
→ Consultez les logs dans GitHub Actions. Si le format est invalide, vous verrez "format_sondage_invalide"

---

## 11. Formats supportés

Le bot supporte maintenant 3 formats de contenu :

| Format | Description | Colonnes requises |
|--------|-------------|-------------------|
| **texte** | Message texte simple | `message` |
| **image** | Image avec légende | `message` (légende), `url` (lien image ou Google Drive) |
| **sondage** | Sondage interactif | `message` (question + options, une par ligne) |

---

## 12. Contact & support

Pour toute question ou assistance :

- Contacter le responsable du projet (`aubinherault64@gmail.com`)

> Projet conçu pour être **maintenable**, **sécurisé**, et **adaptable** sans compétences techniques avancées.