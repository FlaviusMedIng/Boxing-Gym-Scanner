from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from utils.parser import DISTRICTS


def _row_to_dict(row) -> dict:
    return {
        "site": row["site"],
        "title": row["title"] or "(sans titre)",
        "price_chf": row["price_chf"],
        "surface_m2": row["surface_m2"],
        "district": row["district"],
        "possible_changing_room": bool(row["possible_changing_room"]),
        "score": row["score"],
        "matches": bool(row["matches"]),
        "status": row["status"],
        "url": row["url"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
    }


def generate_site(db, config: dict, output_path: str = "docs/index.html") -> None:
    """Génère une page HTML statique et autonome listant les annonces.

    Pensée pour être publiée gratuitement via GitHub Pages (dossier /docs) :
    aucune dépendance externe (CSS/JS inline), un seul fichier, les données
    sont embarquées en JSON et filtrées côté client en JavaScript.
    """
    df = db.dataframe()
    if df.empty:
        rows = []
    else:
        # NaN (colonnes numériques pandas) n'est pas du JSON valide et ferait
        # échouer JSON.parse() côté client : on le remplace par null/None.
        df = df.astype(object).where(df.notna(), None)
        rows = [_row_to_dict(r) for r in df.to_dict("records")]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    criteria = config.get("criteria", {})

    html = _TEMPLATE.replace("__DATA_JSON__", json.dumps(rows, ensure_ascii=False))
    html = html.replace("__GENERATED_AT__", generated_at)
    html = html.replace("__MAX_RENT__", str(criteria.get("max_rent_chf_month", "")))
    html = html.replace("__MIN_SURFACE__", str(criteria.get("min_surface_m2", "")))

    out.write_text(html, encoding="utf-8")


_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Geneva Gym Scanner — Annonces</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #f6f7f9;
    --panel: #ffffff;
    --text: #1c2128;
    --muted: #6b7280;
    --border: #e2e5e9;
    --accent: #2563eb;
    --accent-bg: #eaf1ff;
    --good: #16803c;
    --good-bg: #e8f7ee;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #14161a;
      --panel: #1c1f24;
      --text: #e7e9ec;
      --muted: #9aa1ab;
      --border: #2c3036;
      --accent: #6ea8fe;
      --accent-bg: #1c2b45;
      --good: #4fd88a;
      --good-bg: #123522;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
  }
  header {
    padding: 24px clamp(16px, 4vw, 40px);
    border-bottom: 1px solid var(--border);
    background: var(--panel);
  }
  header h1 { margin: 0 0 4px; font-size: 1.4rem; }
  header p { margin: 0; color: var(--muted); font-size: 0.9rem; }
  main { padding: 20px clamp(16px, 4vw, 40px) 60px; max-width: 1400px; margin: 0 auto; }

  .stats { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
  .stat {
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 10px 16px; min-width: 120px;
  }
  .stat .n { font-size: 1.4rem; font-weight: 600; }
  .stat .l { font-size: 0.78rem; color: var(--muted); }

  .filters {
    display: flex; flex-wrap: wrap; gap: 10px; align-items: end;
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px; margin-bottom: 18px;
  }
  .filters label { display: flex; flex-direction: column; font-size: 0.75rem; color: var(--muted); gap: 4px; }
  .filters input, .filters select {
    font-size: 0.85rem; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--border);
    background: var(--bg); color: var(--text);
  }
  .filters .toggle { flex-direction: row; align-items: center; gap: 6px; }

  .grid {
    display: grid; gap: 12px;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  }
  .card {
    background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
    padding: 14px 16px; display: flex; flex-direction: column; gap: 6px;
  }
  .card.match { border-color: var(--good); box-shadow: 0 0 0 1px var(--good) inset; }
  .card .top { display: flex; justify-content: space-between; align-items: start; gap: 8px; }
  .card .title { font-weight: 600; font-size: 0.95rem; line-height: 1.3; }
  .badge {
    font-size: 0.7rem; padding: 2px 8px; border-radius: 999px; white-space: nowrap;
    background: var(--accent-bg); color: var(--accent); font-weight: 600;
  }
  .badge.good { background: var(--good-bg); color: var(--good); }
  .card .meta { font-size: 0.82rem; color: var(--muted); display: flex; flex-wrap: wrap; gap: 4px 10px; }
  .card .site { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); }
  .card a.cta {
    margin-top: 6px; align-self: start; font-size: 0.85rem; font-weight: 600;
    color: var(--accent); text-decoration: none;
  }
  .card a.cta:hover { text-decoration: underline; }
  .empty { color: var(--muted); padding: 40px; text-align: center; }
</style>
</head>
<body>
<header>
  <h1>Geneva Gym Scanner</h1>
  <p>Dernière mise à jour : __GENERATED_AT__ — critères : loyer ≤ __MAX_RENT__ CHF/mois, surface ≥ __MIN_SURFACE__ m²</p>
</header>
<main>
  <div class="stats" id="stats"></div>

  <div class="filters">
    <label>Recherche
      <input type="text" id="f-text" placeholder="titre, adresse...">
    </label>
    <label>Site
      <select id="f-site"><option value="">Tous</option></select>
    </label>
    <label>Quartier
      <select id="f-district"><option value="">Tous</option></select>
    </label>
    <label>Loyer max (CHF)
      <input type="number" id="f-price" placeholder="ex: 5000">
    </label>
    <label>Surface min (m²)
      <input type="number" id="f-surface" placeholder="ex: 70">
    </label>
    <label>Statut
      <select id="f-status">
        <option value="active" selected>Actives</option>
        <option value="">Toutes (y compris supprimées)</option>
      </select>
    </label>
    <label class="toggle">
      <input type="checkbox" id="f-matches-only" checked>
      Correspond aux critères uniquement
    </label>
  </div>

  <div class="grid" id="grid"></div>
  <div class="empty" id="empty" style="display:none">Aucune annonce ne correspond à ces filtres.</div>
</main>

<script id="data" type="application/json">__DATA_JSON__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);

const els = {
  text: document.getElementById('f-text'),
  site: document.getElementById('f-site'),
  district: document.getElementById('f-district'),
  price: document.getElementById('f-price'),
  surface: document.getElementById('f-surface'),
  status: document.getElementById('f-status'),
  matchesOnly: document.getElementById('f-matches-only'),
  grid: document.getElementById('grid'),
  empty: document.getElementById('empty'),
  stats: document.getElementById('stats'),
};

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, 'fr'));
}

for (const site of uniqueSorted(DATA.map(d => d.site))) {
  const opt = document.createElement('option');
  opt.value = site; opt.textContent = site;
  els.site.appendChild(opt);
}
for (const d of uniqueSorted(DATA.map(d => d.district))) {
  const opt = document.createElement('option');
  opt.value = d; opt.textContent = d;
  els.district.appendChild(opt);
}

function escapeHtml(s) {
  return (s ?? '').toString().replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function render() {
  const text = els.text.value.trim().toLowerCase();
  const site = els.site.value;
  const district = els.district.value;
  const maxPrice = parseFloat(els.price.value);
  const minSurface = parseFloat(els.surface.value);
  const status = els.status.value;
  const matchesOnly = els.matchesOnly.checked;

  const filtered = DATA.filter(d => {
    if (status && d.status !== status) return false;
    if (matchesOnly && !d.matches) return false;
    if (site && d.site !== site) return false;
    if (district && d.district !== district) return false;
    if (!isNaN(maxPrice) && d.price_chf != null && d.price_chf > maxPrice) return false;
    if (!isNaN(minSurface) && d.surface_m2 != null && d.surface_m2 < minSurface) return false;
    if (text && !(d.title || '').toLowerCase().includes(text)) return false;
    return true;
  }).sort((a, b) => (b.score || 0) - (a.score || 0));

  els.stats.innerHTML = `
    <div class="stat"><div class="n">${DATA.length}</div><div class="l">annonces au total</div></div>
    <div class="stat"><div class="n">${DATA.filter(d => d.matches).length}</div><div class="l">correspondent aux critères</div></div>
    <div class="stat"><div class="n">${filtered.length}</div><div class="l">affichées avec ces filtres</div></div>
  `;

  els.grid.innerHTML = filtered.map(d => `
    <div class="card ${d.matches ? 'match' : ''}">
      <div class="top">
        <div>
          <div class="site">${escapeHtml(d.site)}</div>
          <div class="title">${escapeHtml(d.title)}</div>
        </div>
        ${d.matches ? '<span class="badge good">Correspond</span>' : ''}
      </div>
      <div class="meta">
        <span>${d.price_chf != null ? d.price_chf.toLocaleString('fr-CH') + ' CHF/mois' : 'Prix non publié'}</span>
        <span>${d.surface_m2 != null ? d.surface_m2 + ' m²' : 'Surface inconnue'}</span>
        ${d.district ? `<span>${escapeHtml(d.district)}</span>` : ''}
        ${d.possible_changing_room ? '<span class="badge">Vestiaires possibles</span>' : ''}
        ${d.status !== 'active' ? `<span class="badge">${escapeHtml(d.status)}</span>` : ''}
      </div>
      <a class="cta" href="${escapeHtml(d.url)}" target="_blank" rel="noopener">Voir l'annonce →</a>
    </div>
  `).join('');

  els.empty.style.display = filtered.length ? 'none' : 'block';
}

for (const el of [els.text, els.site, els.district, els.price, els.surface, els.status, els.matchesOnly]) {
  el.addEventListener('input', render);
  el.addEventListener('change', render);
}
render();
</script>
</body>
</html>
"""


def generate_criteria_page(config: dict, output_path: str = "docs/criteria.html", worker_url: str = "") -> None:
    """Génère une page de formulaire permettant de modifier les critères de
    recherche (surface, loyer, quartiers, vestiaires) sans compte GitHub ni
    édition manuelle de config.yaml.

    Le formulaire poste au Cloudflare Worker `worker_url`, qui crée une
    issue GitHub ; une GitHub Action applique ensuite l'issue à config.yaml
    (voir scripts/apply_criteria_update.py). L'accès est protégé par un
    jeton passé en query string (`?key=...`, voir CRITERIA_EDIT_TOKEN dans
    main.py) que le Worker vérifie côté serveur — il n'est jamais lu depuis
    le HTML/JS, seulement transmis tel quel.
    """
    criteria = config.get("criteria", {})
    allowed = set(criteria.get("allowed_districts", []))

    district_checkboxes = "\n".join(
        f'''      <label class="chk">
        <input type="checkbox" name="district" value="{d}" {"checked" if d in allowed else ""}>
        {d}
      </label>'''
        for d in DISTRICTS
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    html = _CRITERIA_TEMPLATE.replace("__DISTRICT_CHECKBOXES__", district_checkboxes)
    html = html.replace("__MIN_SURFACE__", str(criteria.get("min_surface_m2", 50)))
    html = html.replace("__MAX_RENT__", str(criteria.get("max_rent_chf_month", 10000)))
    html = html.replace(
        "__CHANGING_ROOM_CHECKED__",
        "checked" if criteria.get("require_possible_changing_rooms", True) else "",
    )
    html = html.replace("__WORKER_URL__", json.dumps(worker_url))

    out.write_text(html, encoding="utf-8")


_CRITERIA_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Geneva Gym Scanner — Modifier les critères</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #f6f7f9; --panel: #ffffff; --text: #1c2128; --muted: #6b7280;
    --border: #e2e5e9; --accent: #2563eb; --good: #16803c; --bad: #b42318;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #14161a; --panel: #1c1f24; --text: #e7e9ec; --muted: #9aa1ab;
      --border: #2c3036; --accent: #6ea8fe; --good: #4fd88a; --bad: #ff8177;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text);
  }
  header { padding: 24px clamp(16px, 4vw, 40px); border-bottom: 1px solid var(--border); background: var(--panel); }
  header h1 { margin: 0 0 4px; font-size: 1.4rem; }
  header p { margin: 0; color: var(--muted); font-size: 0.9rem; }
  header a { color: var(--accent); }
  main { padding: 20px clamp(16px, 4vw, 40px) 60px; max-width: 640px; margin: 0 auto; }
  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
  .field { margin-bottom: 18px; }
  .field label.title { display: block; font-weight: 600; margin-bottom: 6px; font-size: 0.9rem; }
  .field input[type="number"] {
    width: 100%; font-size: 1rem; padding: 8px 10px; border-radius: 8px;
    border: 1px solid var(--border); background: var(--bg); color: var(--text);
  }
  .districts { display: flex; flex-wrap: wrap; gap: 8px 16px; }
  .chk { display: flex; align-items: center; gap: 6px; font-size: 0.9rem; }
  .toggle { display: flex; align-items: center; gap: 8px; font-size: 0.9rem; }
  button {
    width: 100%; padding: 12px; font-size: 1rem; font-weight: 600; border: none;
    border-radius: 8px; background: var(--accent); color: #fff; cursor: pointer; margin-top: 8px;
  }
  button:disabled { opacity: 0.6; cursor: not-allowed; }
  #status { margin-top: 14px; font-size: 0.9rem; }
  #status.ok { color: var(--good); }
  #status.err { color: var(--bad); }
</style>
</head>
<body>
<header>
  <h1>Modifier les critères de recherche</h1>
  <p>Ces changements seront appliqués automatiquement au prochain scan (toutes les 3h). <a href="index.html">← Voir les annonces</a></p>
</header>
<main>
  <div class="panel">
    <form id="f">
      <div class="field">
        <label class="title" for="surface">Surface minimum (m²)</label>
        <input type="number" id="surface" min="1" step="1" value="__MIN_SURFACE__" required>
      </div>
      <div class="field">
        <label class="title" for="rent">Loyer maximum (CHF/mois)</label>
        <input type="number" id="rent" min="1" step="50" value="__MAX_RENT__" required>
      </div>
      <div class="field">
        <div class="title">Quartiers acceptés</div>
        <div class="districts">
__DISTRICT_CHECKBOXES__
        </div>
      </div>
      <div class="field">
        <label class="toggle">
          <input type="checkbox" id="changing-room" __CHANGING_ROOM_CHECKED__>
          N'accepter que les locaux avec vestiaires/sanitaires possibles
        </label>
      </div>
      <button type="submit" id="submit-btn">Envoyer les nouveaux critères</button>
      <div id="status"></div>
    </form>
  </div>
</main>
<script>
const WORKER_URL = __WORKER_URL__;
const key = new URLSearchParams(location.search).get('key') || '';
const statusEl = document.getElementById('status');
const btn = document.getElementById('submit-btn');

if (!key) {
  statusEl.textContent = "Lien invalide : il manque la clé d'accès. Ouvre cette page depuis le lien reçu par email.";
  statusEl.className = 'err';
  btn.disabled = true;
}

document.getElementById('f').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!WORKER_URL) {
    statusEl.textContent = "Le formulaire n'est pas encore configuré côté serveur (Worker manquant).";
    statusEl.className = 'err';
    return;
  }
  btn.disabled = true;
  statusEl.className = '';
  statusEl.textContent = 'Envoi en cours...';

  const districts = [...document.querySelectorAll('input[name="district"]:checked')].map(el => el.value);
  const payload = {
    key,
    min_surface_m2: Number(document.getElementById('surface').value),
    max_rent_chf_month: Number(document.getElementById('rent').value),
    allowed_districts: districts,
    require_possible_changing_rooms: document.getElementById('changing-room').checked,
  };

  try {
    const res = await fetch(WORKER_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.ok) {
      statusEl.textContent = 'Envoyé ! Les nouveaux critères seront actifs au prochain scan (~3h max).';
      statusEl.className = 'ok';
    } else {
      statusEl.textContent = 'Erreur : ' + (data.error || res.statusText);
      statusEl.className = 'err';
      btn.disabled = false;
    }
  } catch (err) {
    statusEl.textContent = 'Erreur réseau, réessaie dans un instant.';
    statusEl.className = 'err';
    btn.disabled = false;
  }
});
</script>
</body>
</html>
"""
