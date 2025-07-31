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
    creds = Credentials.from_service_account_file(config.CHEMIN_CLE_JSON,
                                                  scopes=scope)
    client_gsheets = gspread.authorize(creds)

    # --- Dictionnaire jours FR ---
    jours_fr = {
        "monday": "lundi",
        "tuesday": "mardi",
        "wednesday": "mercredi",
        "thursday": "jeudi",
        "friday": "vendredi",
        "saturday": "samedi",
        "sunday": "dimanche"
    }

    def jour_fr(dt):
        return jours_fr[dt.strftime("%A").lower()]

    # --- Lecture fichier clients ---
    ws_clients = client_gsheets.open(config.FICHIER_CLIENTS).worksheet(
        config.FEUILLE_CLIENTS)
    df_clients = pd.DataFrame(ws_clients.get_all_records())

    # --- Préparation ---
    df_clients["Date de Démarrage"] = pd.to_datetime(
        df_clients["Date de Démarrage"])
    df_clients["Jours de Diffusion"] = df_clients["Jours de Diffusion"].apply(
        lambda x: [j.strip().lower() for j in str(x).split(",")])
    df_clients["Programme"] = df_clients["Programme"].astype(int).apply(
        lambda x: f"{x:03}")
    df_clients["Canal ID"] = df_clients["Canal ID"].astype(str)
    df_clients["Saison"] = df_clients["Saison"].astype(int)

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

    # --- Génération du planning ---
    planning = []
    for _, row in df_filtree.iterrows():
        nom_client = row["Client"]
        programme = row["Programme"]
        saison = int(row["Saison"])
        chat_id = row["Canal ID"]
        date_debut = row["Date de Démarrage"]
        jours_diff = row["Jours de Diffusion"]

        avancement = 0
        for i in range(7):
            date_envoi = date_debut + timedelta(days=i)
            jour_nom = jour_fr(date_envoi)

            if jour_nom in jours_diff:
                avancement += 1
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
                            "envoye": "non"
                        })

    # --- Nouveau planning ---
    df_nouveau = pd.DataFrame(planning)

    # --- Lecture planning existant ---
    ws_planning = client_gsheets.open(config.FICHIER_PLANNING).worksheet(
        config.FEUILLE_PLANNING)
    records = ws_planning.get_all_records()

    if records:
         df_existant = pd.DataFrame(records)
    else:
        df_existant = pd.DataFrame(columns=[
            "client", "programme", "saison", "chat_id", "date", "heure",
            "type", "avancement", "message", "format", "url", "envoye"
        ])


    # --- Uniformisation des types ---
    df_nouveau["programme"] = df_nouveau["programme"].astype(str).apply(
        lambda x: f"{int(x):03}")
    df_existant["programme"] = df_existant["programme"].astype(str).apply(
        lambda x: f"{int(x):03}" if x else "")
    for col in [
            "client", "chat_id", "date", "heure", "type", "message", "envoye"
    ]:
        df_nouveau[col] = df_nouveau[col].astype(str)
        df_existant[col] = df_existant[col].astype(str)

    # --- Fusion sans doublons ---
    df_merge = pd.concat([df_existant, df_nouveau], ignore_index=True)
    df_merge.drop_duplicates(subset=[
        "client", "programme", "saison", "chat_id", "date", "heure", "type"
    ],
                             keep="first",
                             inplace=True)

    # --- Vérifie et ajoute les colonnes format et url si besoin ---
    colonnes_planning = [
        "client", "programme", "saison", "chat_id", "date", "heure",
        "type", "avancement", "message", "format", "url", "envoye"
    ]
    for col in colonnes_planning:
        if col not in df_merge.columns:
            df_merge[col] = ""

    # Réorganise l’ordre des colonnes pour garder la structure propre
    df_merge = df_merge.reindex(columns=colonnes_planning)

    # --- Pré-tri ---
    df_merge["datetime"] = pd.to_datetime(df_merge["date"] + " " +
                                          df_merge["heure"])
    df_merge.sort_values(by="datetime", inplace=True)
    df_merge.drop(columns="datetime", inplace=True)

    # --- Préchargement des programmes ---
    programmes_charges = defaultdict(pd.DataFrame)
    for prog_id in df_merge["programme"].unique():
        try:
            ws = client_gsheets.open(
                config.FICHIER_PROGRAMMES).worksheet(prog_id)
            programmes_charges[prog_id] = pd.DataFrame(ws.get_all_records())
        except:
            programmes_charges[prog_id] = pd.DataFrame()

    # --- Remplissage des messages ---
    type_mapping = {
        "Conseil": "2-Conseil",
        "Aphorisme": "1-Aphorisme",
        "Réflexion": "3-Réflexion"
    }

    messages_remplis = []
    formats_remplis = []
    urls_remplis = []
    for _, row in df_merge.iterrows():
        if pd.notna(row["message"]) and row["message"].strip() != "":
            messages_remplis.append(row["message"])
            formats_remplis.append(row.get("format", "texte"))
            urls_remplis.append(row.get("url", ""))
            continue

        programme = row["programme"]
        saison = int(row["saison"])
        jour = int(row["avancement"])
        type_excel = type_mapping.get(row["type"])
        df_prog = programmes_charges.get(programme, pd.DataFrame())

        filtre = ((df_prog["Saison"] == saison) & (df_prog["Jour"] == jour) &
                  (df_prog["Type"] == type_excel))
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
    ws_planning.clear()
    ws_planning.update([df_merge.columns.values.tolist()] +
                       df_merge.values.tolist())

    paris = pytz.timezone("Europe/Paris")
    print(
        f"📅 Mise à jour planning à {datetime.now(paris).strftime('%Y-%m-%d %H:%M:%S')}"
    )


if __name__ == "__main__":
    generer_planning()
