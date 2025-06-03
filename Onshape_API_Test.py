import os
import time
import hmac
import hashlib
import base64
import requests
from urllib.parse import urlparse
from email.utils import formatdate
from dotenv import load_dotenv

load_dotenv()

ACCESS_KEY = os.getenv("ONSHAPE_ACCESS_KEY")
SECRET_KEY = os.getenv("ONSHAPE_SECRET_KEY")

def build_headers(method, url, access_key, secret_key):
    parsed = urlparse(url)
    path = parsed.path
    query = parsed.query

    nonce = str(int(time.time() * 1000))
    date = formatdate(timeval=None, localtime=False, usegmt=True)
    content_type = "application/json"

    string_to_sign = f"{method}\n{nonce}\n{date}\n{content_type}\n{path}\n{query}\n".lower()
    hmac_digest = hmac.new(secret_key.encode(), string_to_sign.encode(), hashlib.sha256).digest()
    signature = base64.b64encode(hmac_digest).decode()

    return {
        "Authorization": f"On {access_key}:HmacSHA256:{signature}",
        "On-Nonce": nonce,
        "Date": date,
        "Content-Type": content_type,
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
    part_name = "Part 1"
    part_data = data.get("bodies", {}).get(part_name)
    if part_data:
        volume = part_data.get("volume")
        print(f"Volume of '{part_name}': {volume} m^3")
    else:
        print(f"Could not find mass properties for part '{part_name}'.")

if __name__ == "__main__":
    main()
