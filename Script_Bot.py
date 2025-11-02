import os
import time
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import pytz
import requests
import config
import re
import tempfile

# ======================
# Helpers / Parameters
# ======================
DRIVE_FILE_RE = re.compile(
    r"(?:https?://)?(?:drive\.google\.com)/(?:file/d/([a-zA-Z0-9_-]+)|open\?id=([a-zA-Z0-9_-]+))"
)

def extract_drive_file_id(url: str) -> str:
    if not url:
        return ""
    m = DRIVE_FILE_RE.search(url)
    if not m:
        return ""
    return m.group(1) or m.group(2) or ""

def download_drive_file_to_temp(file_id: str) -> str:
    if not file_id:
        raise ValueError("Missing Google Drive file id")

    session = requests.Session()
    base = "https://drive.google.com/uc?export=download"
    params = {"id": file_id}
    r = session.get(base, params=params, stream=True, allow_redirects=True, timeout=15)

    def _find_confirm_token(content_text: str):
        m = re.search(r"confirm=([0-9A-Za-z_]+)", content_text)
        return m.group(1) if m else None

    if ("text/html" in r.headers.get("content-type", "")) and r.text:
        token = _find_confirm_token(r.text)
        if token:
            params["confirm"] = token
            r = session.get(base, params=params, stream=True, allow_redirects=True, timeout=15)

    r.raise_for_status()

    ctype = r.headers.get("content-type", "")
    suffix = ""
    if "jpeg" in ctype:
        suffix = ".jpg"
    elif "png" in ctype:
        suffix = ".png"
    elif "webp" in ctype:
        suffix = ".webp"
    elif "gif" in ctype:
        suffix = ".gif"
    else:
        suffix = ".bin"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        for chunk in r.iter_content(1024 * 64):
            if chunk:
                tmp.write(chunk)
        tmp.flush()
        return tmp.name
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise

def _tz():
    try:
        return pytz.timezone(config.FUSEAU_HORAIRE)
    except Exception:
        return pytz.timezone("Europe/Paris")

TELEGRAM_TOKEN = getattr(config, "TELEGRAM_TOKEN", os.getenv("TELEGRAM_TOKEN", ""))
if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN manquant")

TELEGRAM_TIMEOUT = getattr(config, "TELEGRAM_TIMEOUT", 10)
TELEGRAM_MAX_RETRIES = getattr(config, "TELEGRAM_MAX_RETRIES", 3)
SEND_WINDOW_MINUTES = getattr(config, "SEND_WINDOW_MINUTES", None)

API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def col_idx_to_a1(idx1):
    s = ""
    while idx1 > 0:
        idx1, rem = divmod(idx1 - 1, 26)
        s = chr(65 + rem) + s
    return s

def localize_safe(series_dt_naive, tz):
    return (series_dt_naive
            .dt.tz_localize(tz, ambiguous="infer", nonexistent="shift_forward"))

def send_telegram_message(chat_id, text):
    url = f"{API_BASE}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
    return _post_with_retry(url, payload)

def send_telegram_photo(chat_id, photo, caption=None, is_file=False):
    api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption

    try:
        if is_file:
            files = {"photo": photo}
            r = requests.post(api, data=data, files=files, timeout=20)
        else:
            data["photo"] = photo
            r = requests.post(api, data=data, timeout=20)

        if r.status_code == 200:
            return True, ""
        return False, f"{r.status_code}:{r.text}"
    except Exception as e:
        return False, f"exception:{e}"

def send_telegram_poll(chat_id, question, options, is_anonymous=True, allows_multiple_answers=False):
    url = f"{API_BASE}/sendPoll"
    
    if len(options) > 10:
        return False, "max_10_options"
    
    if len(options) < 2:
        return False, "min_2_options_required"
    
    payload = {
        "chat_id": chat_id,
        "question": question,
        "options": options,
        "is_anonymous": is_anonymous,
        "allows_multiple_answers": allows_multiple_answers,
        "type": "regular"
    }
    
    try:
        r = requests.post(url, json=payload, timeout=TELEGRAM_TIMEOUT)
        
        if r.status_code == 200:
            try:
                data = r.json()
                if data.get("ok"):
                    poll_id = data.get("result", {}).get("poll", {}).get("id", "")
                    return True, poll_id
            except Exception:
                pass
            return True, "ok"
        
        return False, f"{r.status_code}:{r.text}"
        
    except Exception as e:
        return False, f"exception:{e}"

def parse_poll_content(message_text):
    """
    Parse pour format sondage avec date intégrée.
    Format: Ligne 1: Date, Ligne 2: Question, Lignes 3+: Options
    """
    lines = [line.strip() for line in message_text.strip().split("\n") if line.strip()]

    if len(lines) < 4:  # Au minimum: date + question + 2 options
        return None, None

    date = lines[0]
    raw_question = lines[1]
    options = lines[2:]

    # Intégrer date dans question
    question = f"📅 {date}\n\n{raw_question}"

    # Ajouter "Autre :" automatiquement
    options.append("Autre :")

    if len(options) > 10:
        options = options[:10]

    return question, options

def _post_with_retry(url, payload):
    for attempt in range(1, TELEGRAM_MAX_RETRIES + 1):
        try:
            r = requests.post(url, data=payload, timeout=TELEGRAM_TIMEOUT)
        except requests.RequestException as e:
            if attempt >= TELEGRAM_MAX_RETRIES:
                return False, f"request_exception:{e}"
            time.sleep(2 ** attempt)
            continue

        try:
            data = r.json()
        except Exception:
            data = {"ok": False, "error_code": r.status_code, "description": "invalid_json"}

        if r.status_code == 429:
            retry_after = 1
            try:
                retry_after = int(data.get("parameters", {}).get("retry_after", 1))
            except Exception:
                pass
            time.sleep(retry_after + 1)
            continue

        if r.status_code >= 500 and attempt < TELEGRAM_MAX_RETRIES:
            time.sleep(2 ** attempt)
            continue

        if r.ok and data.get("ok", False):
            return True, "ok"

        return False, f"{data.get('error_code','?')}:{data.get('description','unknown')}"

    return False, "max_retries_exceeded"

def process_poll_updates_and_save(client, planning_data):
    """
    Récupère les réponses aux sondages et les enregistre dans Réponses Sondages.
    planning_data: dict avec clés poll_id -> {programme, saison, jour, societe, date_envoi, type_sondage}
    """
    tz = _tz()
    
    try:
        url = f"{API_BASE}/getUpdates"
        params = {"timeout": 5, "allowed_updates": ["poll", "poll_answer"]}
        
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ Erreur getUpdates: {r.status_code}")
            return
        
        data = r.json()
        if not data.get("ok"):
            return
        
        results = data.get("result", [])
        if not results:
            return
        
        # Construire mapping poll_id -> (question, options)
        poll_data = {}
        for update in results:
            if "poll" in update:
                poll = update["poll"]
                poll_id = poll.get("id")
                question = poll.get("question", "")
                options = [opt.get("text", "") for opt in poll.get("options", [])]
                poll_data[poll_id] = (question, options)
        
        # Ouvrir feuille Réponses Sondages
        ws_reponses = client.open(config.FICHIER_PLANNING).worksheet(config.FEUILLE_REPONSES_SONDAGES)
        
        # Vérifier colonnes
        header = ws_reponses.row_values(1)
        expected = ["User ID", "Prénom", "Nom", "Société", "Username", "Date et Heure", 
                   "Date Envoi", "Programme", "Saison", "Jour", "Question", "Réponse(s)", 
                   "Commentaire", "Type Sondage"]
        if not header or header != expected:
            ws_reponses.update("A1", [expected])
        
        nouvelles_reponses = []
        commentaires_pending = {}  # Pour gérer les "Autre :"
        
        for update in results:
            if "poll_answer" not in update:
                continue
            
            poll_answer = update["poll_answer"]
            poll_id = poll_answer.get("poll_id")
            user = poll_answer.get("user", {})
            option_ids = poll_answer.get("option_ids", [])
            
            user_id = user.get("id", "")
            first_name = user.get("first_name", "")
            last_name = user.get("last_name", "")
            username = user.get("username", "")
            
            timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
            
            # Récupérer infos depuis planning_data
            poll_info = planning_data.get(poll_id, {})
            programme = poll_info.get("programme", "")
            saison = poll_info.get("saison", "")
            jour = poll_info.get("jour", "")
            societe = poll_info.get("societe", "")
            date_envoi = poll_info.get("date_envoi", "")
            type_sondage = poll_info.get("type_sondage", "Sondage")
            
            question, options = poll_data.get(poll_id, ("Question inconnue", []))
            
            # Convertir indices en texte
            reponses_texte = []
            autre_selectionne = False
            for idx in option_ids:
                if idx < len(options):
                    opt_text = options[idx]
                    reponses_texte.append(opt_text)
                    if opt_text == "Autre :":
                        autre_selectionne = True
                else:
                    reponses_texte.append(f"Option {idx}")
            
            reponses_str = ", ".join(reponses_texte)
            
            # Si "Autre :" sélectionné, demander commentaire
            if autre_selectionne:
                # Envoyer message pour demander commentaire
                try:
                    chat_id = user_id  # En mode privé
                    send_telegram_message(chat_id, "Pouvez-vous préciser ?")
                    commentaires_pending[user_id] = {
                        "user_id": str(user_id),
                        "prenom": first_name,
                        "nom": last_name,
                        "societe": societe,
                        "username": username,
                        "timestamp": timestamp,
                        "date_envoi": date_envoi,
                        "programme": programme,
                        "saison": saison,
                        "jour": jour,
                        "question": question,
                        "reponse": reponses_str,
                        "type_sondage": type_sondage
                    }
                except Exception as e:
                    print(f"⚠️ Erreur demande commentaire: {e}")
            
            nouvelles_reponses.append([
                str(user_id),
                first_name,
                last_name,
                societe,
                username,
                timestamp,
                date_envoi,
                programme,
                saison,
                jour,
                question,
                reponses_str,
                "",  # Commentaire (sera rempli après)
                type_sondage
            ])
        
        if nouvelles_reponses:
            ws_reponses.append_rows(nouvelles_reponses)
            print(f"📊 {len(nouvelles_reponses)} réponse(s) de sondage enregistrée(s)")
        
        # Confirmer updates
        if results:
            last_update_id = max(u.get("update_id", 0) for u in results)
            requests.get(f"{API_BASE}/getUpdates", params={"offset": last_update_id + 1}, timeout=5)
    
    except Exception as e:
        print(f"⚠️ Erreur traitement réponses: {e}")

# ======================
# Main
# ======================

def lancer_bot():
    tz = _tz()

    # Auth
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(config.CHEMIN_CLE_JSON, scopes=scope)
    client = gspread.authorize(creds)

    # Vérifier/créer feuille Réponses Sondages
    try:
        spreadsheet = client.open(config.FICHIER_PLANNING)
        try:
            spreadsheet.worksheet(config.FEUILLE_REPONSES_SONDAGES)
        except gspread.WorksheetNotFound:
            ws_new = spreadsheet.add_worksheet(title=config.FEUILLE_REPONSES_SONDAGES, rows=1000, cols=14)
            header = ["User ID", "Prénom", "Nom", "Société", "Username", "Date et Heure", 
                     "Date Envoi", "Programme", "Saison", "Jour", "Question", "Réponse(s)", 
                     "Commentaire", "Type Sondage"]
            ws_new.update("A1", [header])
            print(f"✅ Feuille '{config.FEUILLE_REPONSES_SONDAGES}' créée")
    except Exception as e:
        print(f"⚠️ Erreur vérification feuille: {e}")

    # Préparer dict pour tracking polls
    planning_polls = {}  # poll_id -> infos

    # Traiter réponses sondages précédents
    process_poll_updates_and_save(client, planning_polls)

    # Lire planning
    ws_planning = client.open(config.FICHIER_PLANNING).worksheet(config.FEUILLE_PLANNING)

    rows = ws_planning.get_all_values()
    if not rows:
        print("Planning vide.")
        return
    header = rows[0]
    data_rows = rows[1:]
    if not data_rows:
        print("Aucune ligne planning.")
        return

    df = pd.DataFrame(data_rows, columns=header)

    required = ["client","societe","email_client","programme","saison","chat_id","date","heure","type","avancement","message","format","url","envoye"]
    for c in required:
        if c not in df.columns:
            df[c] = ""

    df["programme"] = df["programme"].apply(lambda x: str(x).zfill(3))
    df["saison"] = pd.to_numeric(df["saison"], errors="coerce").fillna(1).astype(int)
    df["avancement"] = pd.to_numeric(df["avancement"], errors="coerce").fillna(1).astype(int)

    def mk_dt(row):
        s = f"{row['date']} {row['heure']}".strip()
        try:
            return pd.to_datetime(s, errors="coerce")
        except Exception:
            return pd.NaT

    df["_dt_naive"] = df.apply(mk_dt, axis=1)
    mask = df["_dt_naive"].notna()
    if mask.any():
        df.loc[mask, "_dt"] = localize_safe(df.loc[mask, "_dt_naive"].astype("datetime64[ns]"), tz)
    else:
        df["_dt"] = pd.NaT

    now_local = datetime.now(tz)

    has_msg = df["message"].astype(str).str.strip() != ""
    
    elig = (
        (df["envoye"].str.lower() == "non")
        & df["_dt"].notna()
        & (df["_dt"] <= now_local)
        & has_msg
    )
    
    if SEND_WINDOW_MINUTES is not None:
        window_start = now_local - timedelta(minutes=int(SEND_WINDOW_MINUTES))
        elig = elig & (df["_dt"] >= window_start)
    
    df_send = df[elig].copy()

    col_map = {name: (i+1) for i, name in enumerate(header)}
    if "envoye" not in col_map:
        raise RuntimeError("Colonne 'envoye' absente")
    envoye_col_idx = col_map["envoye"]
    envoye_col_letter = col_idx_to_a1(envoye_col_idx)

    updates = []
    for idx, row in df_send.iterrows():
        ws_row_num = int(idx) + 2

        chat_id = row["chat_id"]
        raw_text = str(row["message"]).strip()
        fmt = str(row["format"]).strip().lower()
        url = str(row["url"]).strip()
        type_label = str(row["type"]).strip()
        societe = str(row["societe"]).strip()
        programme = str(row["programme"]).strip()
        saison = str(row["saison"]).strip()
        jour = str(row["avancement"]).strip()
        date_envoi = str(row["date"]).strip()
        
        if not raw_text:
            print(f"⏭️ Skip (message vide) ligne {ws_row_num}")
            continue
        
        try:
            # SONDAGES (Type Sondage ou Sondage+)
            if fmt == "sondage":
                question, options = parse_poll_content(raw_text)
                
                if question and options:
                    # Type "Sondage+" = choix multiple, "Sondage" = choix unique
                    allows_multiple = (type_label == "Sondage+")
                    
                    success, poll_id = send_telegram_poll(
                        chat_id, 
                        question, 
                        options,
                        is_anonymous=True,
                        allows_multiple_answers=allows_multiple
                    )
                    
                    # Stocker infos pour récupération réponses
                    if success and poll_id:
                        planning_polls[poll_id] = {
                            "programme": programme,
                            "saison": saison,
                            "jour": jour,
                            "societe": societe,
                            "date_envoi": date_envoi,
                            "type_sondage": type_label
                        }
                else:
                    success = False
                    err = "format_sondage_invalide"
            
            # IMAGES
            elif fmt == "image" and url:
                file_id = extract_drive_file_id(url)
        
                if file_id:
                    local_path = None
                    try:
                        local_path = download_drive_file_to_temp(file_id)
                        with open(local_path, "rb") as f:
                            success, err = send_telegram_photo(chat_id, f, caption=raw_text, is_file=True)
                    finally:
                        if local_path and os.path.exists(local_path):
                            try:
                                os.unlink(local_path)
                            except Exception:
                                pass
                else:
                    ok_image = False
                    try:
                        h = requests.head(url, allow_redirects=True, timeout=7)
                        ctype = h.headers.get("content-type", "")
                        ok_image = ctype.startswith("image/")
                    except Exception:
                        ok_image = False
        
                    if ok_image:
                        success, err = send_telegram_photo(chat_id, url, caption=raw_text)
                    else:
                        text_to_send = f"{raw_text}\n{url}" if url else raw_text
                        success, err = send_telegram_message(chat_id, text_to_send)
            
            # TEXTE
            else:
                text_to_send = raw_text
                if url:
                    text_to_send = f"{text_to_send}\n{url}"
                success, err = send_telegram_message(chat_id, text_to_send)
                
        except Exception as e:
            success = False
            err = f"exception:{e}"

        if success:
            updates.append((ws_row_num, "oui"))
            type_msg = "sondage" if fmt == "sondage" else ("image" if fmt == "image" else "texte")
            print(f"✅ {type_msg.capitalize()} envoyé (ligne {ws_row_num}) -> chat_id={chat_id}")
        else:
            print(f"⚠️ Echec envoi (ligne {ws_row_num}) -> chat_id={chat_id} ; {err}")

    # Batch update
    if updates:
        batch_body = {
            "valueInputOption": "RAW",
            "data": []
        }
        for rownum, value in updates:
            rng = f"{envoye_col_letter}{rownum}:{envoye_col_letter}{rownum}"
            batch_body["data"].append({
                "range": f"{config.FEUILLE_PLANNING}!{rng}",
                "values": [[value]]
            })
        ws_planning.spreadsheet.values_batch_update(batch_body)
        print(f"Marqués 'envoye=oui' pour {len(updates)} ligne(s).")

    print(f"🕒 Terminé à {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")

if __name__ == "__main__":
    lancer_bot()