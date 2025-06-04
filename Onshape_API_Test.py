import os, time, hmac, hashlib, base64, random, string
import requests
from urllib.parse import urlparse
from email.utils import formatdate
from dotenv import load_dotenv
load_dotenv()

ACCESS_KEY = os.getenv("ONSHAPE_ACCESS_KEY")
SECRET_KEY = os.getenv("ONSHAPE_SECRET_KEY")

def _random_nonce(length: int = 25) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=length))

def build_headers(method: str, url: str, access_key: str, secret_key: str) -> dict:
    parsed = urlparse(url)
    path   = parsed.path
    query  = parsed.query or ""

    nonce = _random_nonce()
    date  = formatdate(localtime=False, usegmt=True)
    ctype = ""                         # ← no Content-Type on GET, same as examples from the docs

    string_to_sign = "\n".join([
        method,
        nonce,
        date,
        ctype,
        path,
        query
    ]) + "\n"                          # trailing newline, matching examples from the docs
    string_to_sign = string_to_sign.lower()

    signature = base64.b64encode(
        hmac.new(secret_key.encode(), string_to_sign.encode(), hashlib.sha256).digest()
    ).decode()

    return {
        "Authorization": f"On {access_key}:HmacSHA256:{signature}",
        "On-Nonce": nonce,
        "Date": date,
        "Accept": "application/json"
    }



def get_mass_properties():
    document_id = "7b718c0dc3191700cd403fbd"
    workspace_id = "8cec3b8c55257ff069fa9f7a"
    element_id = "e255150d11253cea80cbf907"

    url = f"https://cad.onshape.com/api/partstudios/d/{document_id}/w/{workspace_id}/e/{element_id}/massproperties"
    headers = build_headers("GET", url, ACCESS_KEY, SECRET_KEY)

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def main():
    data = get_mass_properties()
    print(data)
    part_name = "Part 1"
    part_data = data.get("bodies", {}).get(part_name)
    if part_data:
        volume = part_data.get("volume")
        print(f"Volume of '{part_name}': {volume} m^3")
    else:
        print(f"Could not find mass properties for part '{part_name}'.")

if __name__ == "__main__":
    main()
