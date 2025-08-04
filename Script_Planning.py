import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import config
import pytz

def generer_planning():
    # --- Authentification Google Sheets ---
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(config.CHEMIN_CLE_JSON, scopes=scope)
    client_gsheets = gspread.authorize(creds)

    # --- Dictionnaire jours FR ---
    jours_fr = {
        "monday": "lundi", "tuesday": "mardi", "wednesday": "mercredi",
        "thursday": "jeudi", "friday": "vendredi", "saturday": "samedi", "sunday": "dimanche"
    }
    def jour_fr(dt):
        return jours_fr[dt.strftime("%A").lower()]

    # --- Lecture fichier clients ---
    ws_clients = client_gsheets.open(config.FICHIER_CLIENTS).worksheet(config.FEUILLE_CLIENTS)
    df_clients = pd.DataFrame(ws_clients.get_all_records())

    # --- Préparation ---
    df_clients["Date de Démarrage"] = pd.to_datetime(df_clients["Date de Démarrage"])
    df_clients["Jours de Diffusion"] = df_clients["Jours de Diffusion"].apply(
        lambda x: [j.strip().lower() for j in str(x).split(",")])
    df_clients["Programme"] = df_clients["Programme"].astype(int).apply(lambda x: f"{x:03}")
    df_clients["Canal ID"] = df_clients["Canal ID"].astype(str).str.strip()
    df_clients["Saison"] = df_clients["Saison"].astype(str).str.zfill(1)  # ou zfill(2) si plusieurs saisons

    colonnes_utiles = [
        "Client", "Thème", "Canal ID", "Programme", "Saison",
        "Date de Démarrage", "Jours de Diffusion", "Heure Conseil",
        "Heure Aphorisme", "Heure Réflexion"
    ]
    df_filtree = df_clients[colonnes_utiles]

    # --- Type vers heure ---
    type_to_heure = {
        "Conseil": "Heure Conseil",
        "Aphorisme": "Heure Aphorisme",
        "Réflexion": "Heure Réflexion"
    }
    NB_JOURS = config.NB_JOURS_GENERATION
    paris = pytz.timezone("Europe/Paris")
    aujourdhui = datetime.now(paris).replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = aujourdhui
    window_end = aujourdhui + timedelta(days=NB_JOURS-1, hours=23, minutes=59, seconds=59)

    # --- Génération du planning pour la fenêtre ---
    planning = []
    for _, row in df_filtree.iterrows():
        nom_client = row["Client"]
        programme = row["Programme"]
        saison = row["Saison"]
        chat_id = row["Canal ID"]
        date_debut = row["Date de Démarrage"]
        jours_diff = row["Jours de Diffusion"]

        for i in range(NB_JOURS):
            date_envoi = window_start + timedelta(days=i)
            if date_envoi >= date_debut:
                jour_nom = jour_fr(date_envoi)
                if jour_nom in jours_diff:
                    avancement = (date_envoi - date_debut).days + 1
                    for type_msg, col_heure in type_to_heure.items():
                        heure = row[col_heure]
                        if pd.notna(heure):
                            planning.append({
                                "client": nom_client,
                                "programme": programme,
                                "saison": saison,
                                "chat_id": chat_id,
                                "date": date_envoi.strftime("%Y-%m-%d"),
                                "heure": str(heure),
                                "type": type_msg,
                                "avancement": avancement,
                                "message": "",
                                "format": "",
                                "url": "",
                                "envoye": "non"
                            })

    df_nouveau = pd.DataFrame(planning)

    # --- Lecture planning existant ---
    ws_planning = client_gsheets.open(config.FICHIER_PLANNING).worksheet(config.FEUILLE_PLANNING)
    records = ws_planning.get_all_records()

    colonnes_planning = [
        "client", "programme", "saison", "chat_id", "date", "heure",
        "type", "avancement", "message", "format", "url", "envoye"
    ]

    if records:
        df_existant = pd.DataFrame(records)
    else:
        df_existant = pd.DataFrame(columns=colonnes_planning)

    # --- Uniformisation stricte des types/clés AVANT fusion ---
    for col in ["client", "programme", "saison", "chat_id", "date", "heure", "type"]:
        if col in df_existant.columns:
            df_existant[col] = df_existant[col].astype(str).str.strip()
        if col in df_nouveau.columns:
            df_nouveau[col] = df_nouveau[col].astype(str).str.strip()
    # Programme = tjs 3 chiffres
    df_existant["programme"] = df_existant["programme"].apply(lambda x: str(int(float(x))).zfill(3) if x.replace('.', '', 1).isdigit() else str(x).zfill(3))
    df_nouveau["programme"] = df_nouveau["programme"].apply(lambda x: str(int(float(x))).zfill(3) if x.replace('.', '', 1).isdigit() else str(x).zfill(3))
    # Saison = tjs string (zfill si besoin selon ton usage)
    df_existant["saison"] = df_existant["saison"].astype(str).str.zfill(1)
    df_nouveau["saison"] = df_nouveau["saison"].astype(str).str.zfill(1)

    df_nouveau = df_nouveau.reindex(columns=colonnes_planning)
    df_existant = df_existant.reindex(columns=colonnes_planning)

    # --- Création d'une colonne datetime complète pour le filtre ---
    df_existant['datetime'] = pd.to_datetime(
        df_existant['date'].astype(str) + ' ' + df_existant['heure'].astype(str),
        errors="coerce"
    )
    df_existant['datetime'] = df_existant['datetime'].dt.tz_localize(paris, ambiguous='NaT', nonexistent='NaT')
    window_start_datetime = window_start  # déjà tz-aware
    window_end_datetime = window_end      # déjà tz-aware

    # --- Filtrage : on ne garde que la fenêtre [date+heure] ---
    mask = (
        (df_existant['datetime'] >= window_start_datetime)
        & (df_existant['datetime'] <= window_end_datetime)
    )
    df_existant = df_existant[mask].copy()
    df_existant = df_existant.drop(columns=["datetime"])

    # --- Fusion EXISTANT (donc "oui" conservé) + NOUVEAU ---
    df_merge = pd.concat([df_existant, df_nouveau], ignore_index=True)
    df_merge.drop_duplicates(
        subset=["client", "programme", "saison", "chat_id", "date", "heure", "type"],
        keep="first", inplace=True
    )
    df_merge = df_merge.reindex(columns=colonnes_planning)

    # --- Remplissage des messages, format, url ---
    programmes_charges = defaultdict(pd.DataFrame)
    for prog_id in df_merge["programme"].unique():
        try:
            ws = client_gsheets.open(config.FICHIER_PROGRAMMES).worksheet(prog_id)
            programmes_charges[prog_id] = pd.DataFrame(ws.get_all_records())
        except:
            programmes_charges[prog_id] = pd.DataFrame()

    type_mapping = {"Conseil": "2-Conseil", "Aphorisme": "1-Aphorisme", "Réflexion": "3-Réflexion"}
    messages_remplis, formats_remplis, urls_remplis = [], [], []
    for _, row in df_merge.iterrows():
        if pd.notna(row["message"]) and row["message"].strip() != "":
            messages_remplis.append(row["message"])
            formats_remplis.append(row.get("format", "texte"))
            urls_remplis.append(row.get("url", ""))
            continue
        programme = row["programme"]
        saison = str(row["saison"])
        jour = int(row["avancement"])
        type_excel = type_mapping.get(row["type"])
        df_prog = programmes_charges.get(programme, pd.DataFrame())
        filtre = ((df_prog["Saison"].astype(str) == saison) & (df_prog["Jour"] == jour) & (df_prog["Type"] == type_excel))
        ligne = df_prog[filtre]
        if not ligne.empty:
            phrase = ligne.iloc[0].get("Phrase", "")
            format_msg = ligne.iloc[0].get("Format", "texte").strip().lower()
            url_msg = ligne.iloc[0].get("Url", "")
            messages_remplis.append(f"Jour {jour} : {row['type']} : {phrase}")
            formats_remplis.append(format_msg)
            urls_remplis.append(url_msg)
        else:
            messages_remplis.append("")
            formats_remplis.append("texte")
            urls_remplis.append("")
    df_merge["message"] = messages_remplis
    df_merge["format"] = formats_remplis
    df_merge["url"] = urls_remplis

    # --- Sauvegarde dans Google Sheet ---
    for col in df_merge.columns:
        df_merge[col] = df_merge[col].astype(str)
    ws_planning.clear()
    ws_planning.update([df_merge.columns.values.tolist()] + df_merge.values.tolist())

    print(f"📅 Mise à jour planning à {datetime.now(paris).strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    generer_planning()
