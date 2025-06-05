"""
Very small Flask app for running an Onshape‑based, 60‑minute modelling contest on a LAN.

• Upload a reference image of the drawing people need to model.
• Click the *Start Contest* button – a 60 min countdown begins.
• While the timer is running, participants paste a public Onshape URL and hit *Evaluate*.
• The app fetches mass‑properties exactly like the original Mass_Properties_viewer_flask.py
  and compares them against hard‑coded solution numbers.
• On an exact match it shows a congratulations message; otherwise it shows rejection.

NOTE
====
* Replace the numbers inside SOLUTION with the correct reference values for your contest.
* The auth helpers (build_headers, etc.) were copied verbatim from the working script.
* No database/session handling – state is kept in process memory (fine for a local event).
"""

from flask import (
    Flask, request, render_template_string,
    redirect, url_for
)
import os, hmac, hashlib, base64, random, string, requests
from urllib.parse import urlparse
from email.utils import formatdate
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()                                           # .env support

ACCESS_KEY = os.getenv("ONSHAPE_ACCESS_KEY")
SECRET_KEY = os.getenv("ONSHAPE_SECRET_KEY")

UPLOAD_FOLDER = "static"                                 # where the drawing image lives
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# ────────────────────────────────────────────────────────────────
#  Hard‑coded correct solution values – EDIT THESE
# ────────────────────────────────────────────────────────────────
SOLUTION = {
    "volume": 123456.789,          # in mm³
    "mass": 987.654,               # in g
    "centroid": [10.0, 20.0, 30.0] # X, Y, Z in mm
}

# ────────────────────────────────────────────────────────────────
#  Helpers copied verbatim from the working CLI/Flask script
# ────────────────────────────────────────────────────────────────

def _random_nonce(length: int = 25) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def build_headers(method: str, url: str,
                  access_key: str = ACCESS_KEY,
                  secret_key: str = SECRET_KEY) -> dict:
    parsed = urlparse(url)
    path, query = parsed.path, parsed.query or ""

    nonce = _random_nonce()                           # single nonce
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
        doc  = parts[parts.index('documents') + 1]
        ws   = parts[parts.index('w') + 1]           # could be 'v'
        elem = parts[parts.index('e') + 1]
        return doc, ws, elem
    except (ValueError, IndexError):
        raise ValueError("Invalid Onshape URL")

# ────────────────────────────────────────────────────────────────
#  Flask state
# ────────────────────────────────────────────────────────────────
app          = Flask(__name__)
contest_end  = None       # datetime when contest ends (UTC)
drawing_file = None       # filename inside static/
message      = ""         # feedback shown to users

# ────────────────────────────────────────────────────────────────
#  Utility helpers
# ────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ────────────────────────────────────────────────────────────────
#  Routes
# ────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def index():
    global message

    running = contest_end is not None and datetime.utcnow() < contest_end
    remaining_seconds = int((contest_end - datetime.utcnow()).total_seconds()) if running else 0

    html = render_template_string('''
    <!doctype html>
    <title>Onshape 3D‑Model Contest</title>
    <h2>Onshape 3D‑Model Contest</h2>

    {% if drawing %}
        <p><b>Reference drawing:</b></p>
        <img src="{{ url_for('static', filename=drawing) }}" style="max-width:500px; border:1px solid #ccc; padding:4px;">
    {% else %}
        <form method="post" action="{{ url_for('upload') }}" enctype="multipart/form-data">
            <b>Upload reference drawing:</b>
            <input type="file" name="photo" accept="image/*" required>
            <button type="submit">Upload</button>
        </form>
        <hr>
    {% endif %}

    {% if not running %}
        <form method="post" action="{{ url_for('start') }}">
            <button type="submit" style="font-size:28px; padding:20px 40px;">Start Contest</button>
        </form>
    {% else %}
        <p><b>Time remaining: <span id="count">{{ remaining }}</span></b></p>
        <form method="post" action="{{ url_for('evaluate') }}">
            <input name="link" size="80" placeholder="Paste Onshape public link here" required>
            <button type="submit">Evaluate</button>
        </form>
    {% endif %}

    {% if message %}
        <hr><div>{{ message|safe }}</div>
    {% endif %}

    {% if running %}
    <script>
        var seconds = {{ remaining_seconds }};
        function tick() {
            if (seconds <= 0) { location.reload(); return; }
            seconds--;
            var m = Math.floor(seconds / 60);
            var s = seconds % 60;
            document.getElementById('count').textContent = m + "m " + (s<10?"0":"") + s + "s";
        }
        setInterval(tick, 1000);
    </script>
    {% endif %}
    ''',
        drawing=drawing_file,
        running=running,
        remaining=f"{remaining_seconds//60}m {remaining_seconds%60:02d}s" if running else '',
        remaining_seconds=remaining_seconds,
        message=message
    )

    # reset message after showing it once
    message = ""
    return html


@app.route('/upload', methods=['POST'])
def upload():
    global drawing_file, message
    file = request.files.get('photo')
    if not file or file.filename == "":
        message = "No file selected."
        return redirect(url_for('index'))

    if allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filename = f"drawing.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        drawing_file = filename
        message = "Drawing uploaded successfully."
    else:
        message = "Invalid file type."
    return redirect(url_for('index'))


@app.route('/start', methods=['POST'])
def start():
    global contest_end, message
    contest_end = datetime.utcnow() + timedelta(minutes=60)
    message = "Contest started – good luck!"
    return redirect(url_for('index'))


@app.route('/evaluate', methods=['POST'])
def evaluate():
    global message

    if contest_end is None or datetime.utcnow() >= contest_end:
        message = "Contest is not running."
        return redirect(url_for('index'))

    link = request.form.get('link', '').strip()
    if not link:
        message = "Please provide an Onshape link."
        return redirect(url_for('index'))

    try:
        doc, ws, elem = parse_link(link)
        parts = get_parts(doc, ws, elem)
        if not parts:
            raise ValueError("No parts found in document.")

        # For simplicity evaluate the *first* part only.
        part = parts[0]
        pid  = part.get('partId')

        props = get_mass_props(doc, ws, elem, pid)
        body  = props.get('bodies', {}).get(pid, {})

        volume   = body.get('volume',   props.get('volume',   0.0)) * 1e9      # m³ → mm³
        mass     = body.get('mass',     props.get('mass',     0.0)) * 1000      # kg → g
        centroid = body.get('centroid', props.get('centroid', [0, 0, 0]))
        centroid_mm = [c * 1000 for c in centroid]

        # Exact comparison (adjust tolerances if needed)
        if (abs(volume - SOLUTION['volume']) < 1e-6 and
            abs(mass   - SOLUTION['mass'])   < 1e-6 and
            all(abs(c - s) < 1e-6 for c, s in zip(centroid_mm, SOLUTION['centroid']))):
            message = "<span style='color:green; font-size:20px;'>🎉 Congratulations – perfect match!</span>"
        else:
            message = "<span style='color:red;'>❌ Mass‑properties do not match.</span>"
    except Exception as exc:
        message = f"<span style='color:red;'>Error: {exc}</span>"

    return redirect(url_for('index'))


# ────────────────────────────────────────────────────────────────
#  Application entry‑point
# ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
