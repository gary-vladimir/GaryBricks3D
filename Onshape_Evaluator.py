from flask import Flask, request, render_template_string
import os, hmac, hashlib, base64, random, string, requests
from urllib.parse import urlparse
from email.utils import formatdate
from dotenv import load_dotenv

load_dotenv()                                       # .env support

ACCESS_KEY = os.getenv("ONSHAPE_ACCESS_KEY")
SECRET_KEY = os.getenv("ONSHAPE_SECRET_KEY")

app = Flask(__name__)

# ------------------------------------------------------------------
#  Helpers copied from the working CLI script
# ------------------------------------------------------------------
def _random_nonce(length: int = 25) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def build_headers(method: str, url: str,
                  access_key: str = ACCESS_KEY,
                  secret_key: str = SECRET_KEY) -> dict:
    parsed = urlparse(url)
    path, query = parsed.path, parsed.query or ""

    nonce = _random_nonce()                         # single nonce
    date  = formatdate(localtime=False, usegmt=True)
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
        hmac.new(secret_key.encode(),
                 string_to_sign.lower().encode(),
                 hashlib.sha256).digest()
    ).decode()

    return {
        "Authorization": f"On {access_key}:HmacSHA256:{signature}",
        "On-Nonce": nonce,                          # same nonce!
        "Date": date,
        "Accept": "application/json"
    }

def get_json(url: str) -> dict:
    res = requests.get(url, headers=build_headers("GET", url))
    res.raise_for_status()
    return res.json()

def get_parts(doc, ws, elem):
    return get_json(f"https://cad.onshape.com/api/parts/d/{doc}/w/{ws}/e/{elem}")

def get_mass_props(doc, ws, elem, pid):
    return get_json(f"https://cad.onshape.com/api/parts/d/{doc}/w/{ws}/e/{elem}/partid/{pid}/massproperties")

def chunk_list(lst, n):                             # same as CLI
    return [lst[i:i+n] for i in range(0, len(lst), n)]

def parse_link(link: str):
    parts = urlparse(link).path.strip('/').split('/')
    try:
        doc = parts[parts.index('documents') + 1]
        ws  = parts[parts.index('w') + 1]           # could be 'v'
        elem = parts[parts.index('e') + 1]
        return doc, ws, elem
    except (ValueError, IndexError):
        raise ValueError("Invalid Onshape URL")

# ------------------------------------------------------------------
#  Flask route
# ------------------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    result_html = ""
    if request.method == 'POST':
        try:
            doc, ws, elem = parse_link(request.form['link'].strip())
            for part in get_parts(doc, ws, elem):
                pid   = part.get("partId")
                name  = part.get("name")

                props = get_mass_props(doc, ws, elem, pid)
                body  = props.get("bodies", {}).get(pid, {})

                vol_arr   = body.get("volume",   props.get("volume", []))
                cent_arr  = body.get("centroid", props.get("centroid", []))
                mass_arr  = body.get("mass",     props.get("mass", []))

                volumes   = vol_arr if isinstance(vol_arr, list) else [vol_arr]
                centroids = chunk_list(cent_arr, 3) if isinstance(cent_arr, list) else [[0,0,0]]
                masses    = mass_arr if isinstance(mass_arr, list) else [mass_arr]

                if volumes and centroids and masses:
                    volume_mm3 = volumes[0] * 1e9
                    x_mm, y_mm, z_mm = [c * 1000 for c in centroids[0]]
                    mass_g = masses[0] * 1000

                    result_html += (
                        f"<p><b>{name}</b><br>"
                        f"Volume: {volume_mm3:.5f} mm³<br>"
                        f"Mass: {mass_g:.5f} g<br>"
                        f"COM: X={x_mm:.5f} mm • Y={y_mm:.5f} mm • Z={z_mm:.5f} mm</p>"
                    )
                else:
                    result_html += f"<p><b>{name}</b><br>Mass-properties unavailable.</p>"
        except Exception as exc:
            result_html = f"<p style='color:red'>Error: {exc}</p>"

    return render_template_string('''
        <!doctype html>
        <title>Onshape Mass-Properties Viewer</title>
        <h2>Onshape Mass-Properties Viewer</h2>
        <form method="post">
            Onshape public link:&nbsp;
            <input name="link" size="80" required>
            <button type="submit">Get Properties</button>
        </form>
        <hr>
        <div>{{ result|safe }}</div>
    ''', result=result_html)

# ------------------------------------------------------------------
if __name__ == '__main__':
    # Debug server – use gunicorn/uwsgi for production.
    app.run(host='0.0.0.0', port=5000, debug=True) 
