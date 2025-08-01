import pandas as pd
import requests
from datetime import datetime
import pytz
import config
import gspread
from google.oauth2.service_account import Credentials

def lancer_bot():
    # --- Authentification Google Sheets ---
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(config.CHEMIN_CLE_JSON, scopes=scope)
    client_gsheets = gspread.authorize(creds)

    # --- Accès au fichier Planning ---
    ws_planning = client_gsheets.open(config.FICHIER_PLANNING).worksheet(config.FEUILLE_PLANNING)
    df = pd.DataFrame(ws_planning.get_all_records())

    # --- Vérification des colonnes minimales ---
    for col in ['date', 'heure', 'chat_id', 'message', 'envoye', 'format', 'url']:
        if col not in df.columns:
            df[col] = ""

    # --- Heure actuelle ---
    paris = pytz.timezone("Europe/Paris")
    maintenant = datetime.now(paris)
    
    # Création de la colonne datetime
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['heure'], errors="coerce")
    df['datetime'] = df['datetime'].dt.tz_localize(paris, ambiguous='NaT', nonexistent='NaT')

    #Gestion des erreurs
    for idx, row in df.iterrows():
        ligne_excel = idx + 1
        if pd.isna(row['datetime']):
            print(f"⚠️ Ligne {ligne_excel} ignorée (date/heure NaT ou mal formée)")
    # --- Filtrage ---
    a_envoyer = df[(df['envoye'].str.lower() == 'non') & (df['datetime'] <= maintenant)]
    print(f"\U0001F4E4 {len(a_envoyer)} message(s) à envoyer...")

    # --- Envoi des messages avec gestion de format ---
    for i, row in a_envoyer.iterrows():
        ligne_excel = i + 2  # ligne réelle dans Google Sheets (header +1)
        try:
            # Check des champs obligatoires
            if pd.isna(row["chat_id"]) or str(row["chat_id"]).strip() in ["", "nan", "None"]:
                print(f"⚠️ Ligne {ligne_excel} ignorée (chat_id manquant)")
                continue
            if pd.isna(row["message"]) or str(row["message"]).strip() == "":
                continue

            chat_id = str(row["chat_id"])
            texte = row.get("message", "")
            format_msg = row.get("format", "").strip().lower()
            url_media = row.get("url", "").strip()

            # Envoi selon le format
            if format_msg == "image" and url_media:
                url_api = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendPhoto"
                payload = {'chat_id': chat_id, 'caption': texte, 'photo': url_media}
            else:
                # Texte ou format non reconnu : concatène le lien s'il existe
                if url_media:
                    texte_final = f"{texte}\n{url_media}"
                else:
                    texte_final = texte
                url_api = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
                payload = {'chat_id': chat_id, 'text': texte_final}

            r = requests.post(url_api, data=payload)
            print(f"✅ Envoyé à {chat_id} [{format_msg}] : {texte[:30]}{'...' if len(texte)>30 else ''}")
            df.at[i, 'envoye'] = 'oui'
            
        except Exception as e:
            print(f"🚨 Ligne {ligne_excel} ignorée pour erreur : {str(e)} | Données : {row.to_dict()}")
            continue  # Continue sur la ligne suivante, ne bloque jamais le bot !

    # --- Nettoyage et types ---
    df.drop(columns="datetime", inplace=True)
    df["chat_id"] = df["chat_id"].astype(str)
    df["envoye"] = df["envoye"].fillna("non")
    df["programme"] = df["programme"].astype(str).str.zfill(3)

    # --- Sauvegarde dans Google Sheets ---
    ws_planning.clear()
    ws_planning.update([df.columns.values.tolist()] + df.values.tolist())

    print("✅ Fichier planning mis à jour après envois.")
    print("Heure actuelle : ", maintenant.strftime("%Y-%m-%d %H:%M:%S"))

if __name__ == "__main__":
    lancer_bot()
