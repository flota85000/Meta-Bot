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
    """
    Extrait l'ID Google Drive à partir de liens de type:
    - https://drive.google.com/file/d/<FILE_ID>/view?...
    - https://drive.google.com/open?id=<FILE_ID>
    Retourne "" si non reconnu.
    """
    if not url:
        return ""
    m = DRIVE_FILE_RE.search(url)
    if not m:
        return ""
    return m.group(1) or m.group(2) or ""

def download_drive_file_to_temp(file_id: str) -> str:
    """
    Télécharge un fichier Google Drive public via 'uc?export=download&id=...' dans un fichier temporaire.
    Gère le token de confirmation pour les redirections/scan antivirus de Drive.
    Retourne le chemin local du fichier temporaire (à supprimer ensuite).
    Lève une Exception en cas d'échec.
    """
    if not file_id:
        raise ValueError("Missing Google Drive file id")

    session = requests.Session()
    base = "https://drive.google.com/uc?export=download"
    params = {"id": file_id}
    r = session.get(base, params=params, stream=True, allow_redirects=True, timeout=15)

    # Si Drive renvoie une page HTML de confirmation, récupérer le token 'confirm'
    def _find_confirm_token(content_text: str):
        # cherche un paramètre confirm=XYZ dans la page
        m = re.search(r"confirm=([0-9A-Za-z_]+)", content_text)
        return m.group(1) if m else None

    if ("text/html" in r.headers.get("content-type", "")) and r.text:
        token = _find_confirm_token(r.text)
        if token:
            params["confirm"] = token
            r = session.get(base, params=params, stream=True, allow_redirects=True, timeout=15)

    r.raise_for_status()

    # Déterminer une extension selon le content-type si possible
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
        # inconnu : tente .bin (Telegram s’en fiche si c’est bien une image)
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
    raise RuntimeError("TELEGRAM_TOKEN manquant (config.py ou variable d'env).")

TELEGRAM_TIMEOUT = getattr(config, "TELEGRAM_TIMEOUT", 10)  # seconds
TELEGRAM_MAX_RETRIES = getattr(config, "TELEGRAM_MAX_RETRIES", 3)
SEND_WINDOW_MINUTES = getattr(config, "SEND_WINDOW_MINUTES", None)  # None = pas de fenêtre

API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def col_idx_to_a1(idx1):
    # idx1 is 1-based index -> column letters (A, B, ... AA, AB ...)
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
    """
    photo: soit une URL (str), soit un fichier binaire (file-like) si is_file=True
    """
    api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption

    try:
        if is_file:
            files = {"photo": photo}  # file-like object
            r = requests.post(api, data=data, files=files, timeout=20)
        else:
            data["photo"] = photo     # URL
            r = requests.post(api, data=data, timeout=20)

        if r.status_code == 200:
            return True, ""
        return False, f"{r.status_code}:{r.text}"
    except Exception as e:
        return False, f"exception:{e}"


def _post_with_retry(url, payload):
    # Retries for 429 / certain 5xx
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

        # Other client errors: no retry
        return False, f"{data.get('error_code','?')}:{data.get('description','unknown')}"

    return False, "max_retries_exceeded"

# ======================
# Main
# ======================

def lancer_bot():
    tz = _tz()

    # Auth Sheets
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(config.CHEMIN_CLE_JSON, scopes=scope)
    client = gspread.authorize(creds)

    # Open planning
    ws_planning = client.open(config.FICHIER_PLANNING).worksheet(config.FEUILLE_PLANNING)

    # Read all records + header to compute row numbers
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

    # Ensure required columns exist
    required = ["client","programme","saison","chat_id","date","heure","type","avancement","message","format","url","envoye"]
    for c in required:
        if c not in df.columns:
            df[c] = ""

    # Normalize types
    df["programme"] = df["programme"].apply(lambda x: str(x).zfill(3))
    df["saison"] = pd.to_numeric(df["saison"], errors="coerce").fillna(1).astype(int)
    df["avancement"] = pd.to_numeric(df["avancement"], errors="coerce").fillna(1).astype(int)

    # Build datetime
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

    # Filter candidates: envoye == "non" and datetime <= now (optionally within window)
    has_msg = df["message"].astype(str).str.strip() != ""
    
    elig = (
        (df["envoye"].str.lower() == "non")
        & df["_dt"].notna()
        & (df["_dt"] <= now_local)
        & has_msg             # <<--- AJOUT
    )
    
    if SEND_WINDOW_MINUTES is not None:
        window_start = now_local - timedelta(minutes=int(SEND_WINDOW_MINUTES))
        elig = elig & (df["_dt"] >= window_start)
    
    df_send = df[elig].copy()

    # Column indices (1-based) for A1 ranges
    col_map = {name: (i+1) for i, name in enumerate(header)}
    if "envoye" not in col_map:
        raise RuntimeError("Colonne 'envoye' absente de la feuille planning.")
    envoye_col_idx = col_map["envoye"]
    envoye_col_letter = col_idx_to_a1(envoye_col_idx)

    # Send loop
    updates = []  # list of (row_index_1based, value)
    for idx, row in df_send.iterrows():
        # Worksheet row number = idx in df + header row (1) + 1
        ws_row_num = int(idx) + 2

        chat_id = row["chat_id"]
        raw_text = str(row["message"]).strip()  # on teste le "message" du planning, pas le texte après append url
        fmt = str(row["format"]).strip().lower()
        url = str(row["url"]).strip()
        
        # Ne rien envoyer si message vide
        if not raw_text:
            print(f"⏭️ Skip (message vide) ligne {ws_row_num} -> chat_id={chat_id}")
            continue
        
        try:
            if fmt == "image" and url:
                file_id = extract_drive_file_id(url)
        
                if file_id:
                    # Cas Google Drive: on télécharge puis on upload à Telegram
                    local_path = None
                    try:
                        local_path = download_drive_file_to_temp(file_id)
                        # send_telegram_photo doit accepter un InputFile; si tu as déjà une fonction utilitaire
                        # 'send_telegram_photo' qui accepte 'files', utilise-la. Sinon en brut:
                        with open(local_path, "rb") as f:
                            # Ex: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", data={...}, files={"photo": f})
                            success, err = send_telegram_photo(chat_id, f, caption=raw_text, is_file=True)
                    finally:
                        if local_path and os.path.exists(local_path):
                            try:
                                os.unlink(local_path)
                            except Exception:
                                pass
        
                else:
                    # Pas un lien Drive -> tentative "URL directe"
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
                        # fallback : on envoie en texte + lien
                        text_to_send = f"{raw_text}\n{url}" if url else raw_text
                        success, err = send_telegram_message(chat_id, text_to_send)
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
            print(f"✅ Envoyé (ligne {ws_row_num}) -> chat_id={chat_id}")
        else:
            print(f"⚠️ Echec envoi (ligne {ws_row_num}) -> chat_id={chat_id} ; {err}")

    # Batch update only changed 'envoye' cells
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
