# MetaBot – Assistant d'envoi Telegram automatique

## Description

**MetaBot** est un assistant automatisé hébergé sur **Replit**. Il gère la planification et l’envoi de messages dans différents canaux Telegram, en fonction d’un programme défini dans Google Sheets.

Il se compose de 2 scripts automatisés :

1. `Script_Planning.py` – Met à jour le planning de messages chaque jour.
2. `Script_Bot.py` – Envoie les messages Telegram toutes les heures selon le planning.

---

## Structure des fichiers

| Fichier                      | Rôle                                                                                   |
| -----------------------------| -------------------------------------------------------------------------------------- |
| `main.py`                    | Serveur Flask pour exécuter manuellement les scripts depuis une URL sécurisée          |
| `Script_Planning.py`         | Génère le fichier de planning depuis les données clients + programme                   |
| `Script_Bot.py`              | Envoie les messages Telegram à l’heure prévue                                          |
| `config.py`                  | Contient tous les paramètres modifiables (tokens, noms de fichiers, noms des feuilles) |
| `google_service_account.json`| Clé pour la connection à google drive. Connection via l'API sur google cloud           |
| `.replit`                    | Configuration du projet Replit et automatisations programmées                          |

---

## Tâches automatisées

| Action                  | Fréquence    | Détails                                                         |
| ----------------------- | ------------ | --------------------------------------------------------------- |
|  Génération du planning | 1× par jour  | Tous les jours à 02h01 UTC (`Script_Planning.py`)               |
|  Envoi des messages     | Chaque heure | À chaque `hh:01` (`Script_Bot.py`)                              |
|  Sécurité des scripts   | Manuelle     | Exécution possible par URL avec token sécurisé (`/run/<token>`) |
|  Pas de doublons        | Automatique  | Ne réécrit pas les messages déjà envoyés (colonne `envoye`)     |


## Fonctionnement du Script Planning
Pour chaque client :
*Extraire les infos du client dans le suivi par client (ex : jour de diffusion, heure pour chaque type de message, programme, saison)
*Extraire le programme dans le fichier Meta-université (ex : programme 002 → feuille 002)
*Pour chaque message dans la feuille de programme extraire : jour, saison, message, type
*Associer ce jour au jour de programme + date de démarrage en sautant les jours non diffusés
*Déterminer le type de message pour l'heure : conseil matin, aphorisme, réflexion
*Créer une ligne dans le planning pour chaque envoie (avec client, programme, saison, date, heure, chat_id, message, envoyé = "non")
*Si la ligne existait déjà la supprimer (suppression des doublons)
*Permet de mettre a jour le fichier sans remettre les messages deja envoyé

## Configuration (`config.py`)

Mettre toutes les infos necessaire : noms des fichiers, noms des feuilles, token telegram, Clé google le .json

## Tests manuels

> Pour exécuter les scripts manuellement via navigateur :

https://<TON-URL-REPLIT>/run/<TON_SECRET_TOKEN>
Exécute `Script_Bot.py`

https://<TON-URL-REPLIT>/run_planning/<TON_SECRET_TOKEN>
Exécute `Script_Planning.py`

---

## En cas de problème

* **Message non envoyé ?**

  * Vérifie que `date` et `heure` sont valides dans la feuille Planning
  * Vérifie que `envoye = non`
  * Consulte les logs

* **Message manquant dans le planning ?**

  * Vérifie que la feuille Programme contient bien la ligne pour le jour + type
  * Vérifie que le nom de la feuille correspond au `programme` du client (ex. "002", "010", etc.)

---

## Améliorations prévues

| Tâche                                                                                   | Statut     |
| --------------------------------------------------------------------------------------- | ---------- |
| Automatisations dans Replit (.replit + cron)                                            | Fait       |
| Ajouter un fichier **log.txt** d’erreurs                                                | À faire    |
| Envoyer un **rapport automatique tous les matins à 8h** dans un canal admin Telegram    | À faire    |
| Centralisation des tokens et paramètres dans `config.py`                                | Fait       |
| Ajout de messages dynamiques personnalisés (optionnel)                                  | À discuter |

---

## Destiné à

* Ce projet peut être géré sans connaissances techniques après configuration.
* Le fichier `config.py` permet de modifier les paramètres facilement.
* Le suivi peut être fait depuis Google Sheets, sans interaction directe avec le code.

---

## Besoin d’aide ? Toutes les explications sont intégrées dans le projet. Sinon, contacter le développeur 😉
