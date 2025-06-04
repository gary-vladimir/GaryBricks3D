import os, hmac, hashlib, base64, random, string
import requests
from urllib.parse import urlparse
from email.utils import formatdate
from dotenv import load_dotenv

load_dotenv()

ACCESS_KEY = os.getenv("ONSHAPE_ACCESS_KEY")
SECRET_KEY = os.getenv("ONSHAPE_SECRET_KEY")

DOCUMENT_ID = "7b718c0dc3191700cd403fbd"
WORKSPACE_ID = "8cec3b8c55257ff069fa9f7a"
ELEMENT_ID = "e255150d11253cea80cbf907"

def _random_nonce(length: int = 25) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

def build_headers(method: str, url: str, access_key: str, secret_key: str) -> dict:
    parsed = urlparse(url)
    path = parsed.path
    query = parsed.query or ""

    nonce = _random_nonce()
    date = formatdate(localtime=False, usegmt=True)
    ctype = ""

    string_to_sign = "\n".join([
        method,
        nonce,
        date,
        ctype,
        path,
        query
    ]) + "\n"

    signature = base64.b64encode(
        hmac.new(secret_key.encode(), string_to_sign.lower().encode(), hashlib.sha256).digest()
    ).decode()

    return {
        "Authorization": f"On {access_key}:HmacSHA256:{signature}",
        "On-Nonce": nonce,
        "Date": date,
        "Accept": "application/json"
    }

def get_parts():
    url = f"https://cad.onshape.com/api/parts/d/{DOCUMENT_ID}/w/{WORKSPACE_ID}/e/{ELEMENT_ID}"
    headers = build_headers("GET", url, ACCESS_KEY, SECRET_KEY)

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_mass_properties_for_part(part_id):
    url = f"https://cad.onshape.com/api/parts/d/{DOCUMENT_ID}/w/{WORKSPACE_ID}/e/{ELEMENT_ID}/partid/{part_id}/massproperties"
    headers = build_headers("GET", url, ACCESS_KEY, SECRET_KEY)

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def main():
    parts = get_parts()

    print("Individual part volumes:\n")
    for part in parts:
        part_id = part.get("partId")
        name = part.get("name")

        mass_properties = get_mass_properties_for_part(part_id)
        volume = mass_properties.get("bodies", {}).get(part_id, {}).get("volume", "N/A")

        print(f"Part: {name} (ID: {part_id}) -> Volume: {volume}")

if __name__ == "__main__":
    main()
