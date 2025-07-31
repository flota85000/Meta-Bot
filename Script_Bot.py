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

    # --- Envoi des messages ---
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"

    for i, row in a_envoyer.iterrows():
        chat_id = str(row["chat_id"])
        texte = row["message"]

        payload = {'chat_id': chat_id, 'text': texte}

        r = requests.post(url, data=payload)
        if r.status_code == 200:
            print(f"✅ Envoyé à {chat_id} : {texte[:30]}...")
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
