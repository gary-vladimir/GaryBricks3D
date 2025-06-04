from flask import Flask, request, render_template_string
import os, hmac, hashlib, base64, random, string
import requests
from urllib.parse import urlparse
from email.utils import formatdate

app = Flask(__name__)

ACCESS_KEY = os.getenv("ONSHAPE_ACCESS_KEY")
SECRET_KEY = os.getenv("ONSHAPE_SECRET_KEY")

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

def get_parts(document_id, workspace_id, element_id):
    url = f"https://cad.onshape.com/api/parts/d/{document_id}/w/{workspace_id}/e/{element_id}"
    headers = build_headers("GET", url, ACCESS_KEY, SECRET_KEY)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_mass_properties(document_id, workspace_id, element_id, part_id):
    url = f"https://cad.onshape.com/api/parts/d/{document_id}/w/{workspace_id}/e/{element_id}/partid/{part_id}/massproperties"
    headers = build_headers("GET", url, ACCESS_KEY, SECRET_KEY)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def parse_ids_from_url(link):
    parts = link.split('/')
    return parts[4], parts[6], parts[8]  # doc_id, workspace_id, elem_id

@app.route('/', methods=['GET', 'POST'])
def index():
    result = ""
    if request.method == 'POST':
        link = request.form.get('link')
        try:
            doc_id, ws_id, elem_id = parse_ids_from_url(link)
            parts = get_parts(doc_id, ws_id, elem_id)
            for part in parts:
                part_id = part.get("partId")
                name = part.get("name")
                mass_props = get_mass_properties(doc_id, ws_id, elem_id, part_id)
                body = mass_props.get("bodies", {}).get(part_id, {})
                volume = body.get("volume", mass_props.get("volume", [0]))[0] * 1e9
                centroid = body.get("centroid", mass_props.get("centroid", [0, 0, 0]))
                mass = body.get("mass", mass_props.get("mass", [0]))[0] * 1000
                x, y, z = [round(c * 1000, 5) for c in centroid]
                result += f"<p><b>{name}</b><br>Volume: {volume:.5f} mm³<br>Mass: {mass:.5f} g<br>COM: X={x} Y={y} Z={z} mm</p>"
        except Exception as e:
            result = f"<p style='color:red'>Error: {e}</p>"

    return render_template_string('''
        <h2>Onshape Mass Properties Viewer</h2>
        <form method="post">
            Onshape Public Link: <input name="link" size="80">
            <input type="submit" value="Get Properties">
        </form>
        <div>{{ result|safe }}</div>
    ''', result=result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
