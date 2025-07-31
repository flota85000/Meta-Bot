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
    creds = Credentials.from_service_account_file(config.CHEMIN_CLE_JSON,
                                                  scopes=scope)
    client_gsheets = gspread.authorize(creds)

    # --- Accès au fichier Planning ---
    ws_planning = client_gsheets.open(config.FICHIER_PLANNING).worksheet(
        config.FEUILLE_PLANNING)
    df = pd.DataFrame(ws_planning.get_all_records())

    # --- Heure actuelle ---
    paris = pytz.timezone("Europe/Paris")
    maintenant = datetime.now(paris)
    df['datetime'] = pd.to_datetime(df['date'] + ' ' +
                                    df['heure']).dt.tz_localize(paris)

    # --- Filtrage ---
    a_envoyer = df[(df['envoye'].str.lower() == 'non')
                   & (df['datetime'] <= maintenant)]
    print(f"\U0001F4E4 {len(a_envoyer)} message(s) à envoyer...")

    # --- Envoi des messages avec gestion de format ---
    for i, row in a_envoyer.iterrows():
        chat_id = str(row["chat_id"])
        texte = row.get("message", "")
        format_msg = row.get("format", "").strip().lower()
        url_media = row.get("url", "").strip()

        # Envoi selon le format
        if format_msg == "image" and url_media:
            url_api = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendPhoto"
            payload = {'chat_id': chat_id, 'caption': texte, 'photo': url_media}
        elif format_msg == "video" and url_media:
            url_api = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendVideo"
            payload = {'chat_id': chat_id, 'caption': texte, 'video': url_media}
        elif format_msg == "audio" and url_media:
            url_api = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendAudio"
            payload = {'chat_id': chat_id, 'caption': texte, 'audio': url_media}
        else:  # Cas texte ou format non reconnu ou pas d'URL
            url_api = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
            payload = {'chat_id': chat_id, 'text': texte}

        r = requests.post(url_api, data=payload)
        if r.status_code == 200:
            print(f"✅ Envoyé à {chat_id} [{format_msg}] : {texte[:30]}{'...' if len(texte)>30 else ''}")
            df.at[i, 'envoye'] = 'oui'
        else:
            print(f"❌ Erreur à {chat_id} : {r.text}")

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
