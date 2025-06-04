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

def chunk_list(lst, chunk_size):
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def main():
    parts = get_parts()
    print("Individual part volumes and centers of mass:\n")

    for part in parts:
        part_id = part.get("partId")
        name = part.get("name")

        mass_properties = get_mass_properties_for_part(part_id)
        volume_array = mass_properties.get("bodies", {}).get(part_id, {}).get("volume", [])
        centroid_array = mass_properties.get("bodies", {}).get(part_id, {}).get("centroid", [])
        mass_array = mass_properties.get("bodies", {}).get(part_id, {}).get("mass", [])
        # Fallback if part_id key doesn't exist in 'bodies'
        if not volume_array or not centroid_array or not mass_array:
            # Use the global flattened volume/centroid arrays
            volume_array = mass_properties.get("volume", [])
            centroid_array = mass_properties.get("centroid", [])
            mass_array = mass_properties.get("mass", [])
        volumes = volume_array if isinstance(volume_array, list) else []
        centroids = chunk_list(centroid_array, 3) if isinstance(centroid_array, list) else []

        if volumes and centroids and mass_array:
            volume_mm3 = volumes[0] * 1e9
            x_mm, y_mm, z_mm = [0.0 if abs(coord * 1000) < 1e-8 else coord * 1000 for coord in centroids[0]]
            mass_grams = mass_array[0] * 1000

            formatted_volume = f"{volume_mm3:.5f} mm³"
            formatted_com = f"X: {x_mm:.5f} mm Y: {y_mm:.5f} mm Z: {z_mm:.5f} mm"
            formatted_mass = f"{mass_grams:.5f} g"

            print(f"Part: {name} (ID: {part_id}) -> Volume: {formatted_volume}, Center of Mass: {formatted_com}, Mass: {formatted_mass}")
        else:
            print(f"Part: {name} (ID: {part_id}) -> Volume: N/A, Center of Mass: N/A, Mass: N/A")

if __name__ == "__main__":
    main()
