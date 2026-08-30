/**
 * Cloudflare Worker: reçoit la soumission du formulaire docs/criteria.html
 * et crée une issue GitHub avec les nouveaux critères. Une GitHub Action
 * (.github/workflows/apply-criteria.yml) lit ensuite cette issue et met à
 * jour config.yaml automatiquement.
 *
 * Ce Worker est le seul endroit qui détient un token GitHub capable
 * d'écrire sur le repo — il n'est jamais exposé au client. La page HTML
 * n'envoie qu'une clé d'accès partagée (CRITERIA_EDIT_TOKEN) que ce Worker
 * compare à son propre secret EXPECTED_KEY avant de faire quoi que ce soit.
 *
 * Secrets à configurer une fois (voir README.md) :
 *   wrangler secret put EXPECTED_KEY     # = valeur du secret GitHub CRITERIA_EDIT_TOKEN
 *   wrangler secret put GITHUB_TOKEN     # PAT fine-grained, permission Issues: write uniquement, sur ce repo
 * Variable non secrète (dans wrangler.toml) : GITHUB_REPO = "FlaviusMedIng/Boxing-Gym-Scanner"
 */

// Copie obligatoire de utils/parser.py::DISTRICTS — un Worker Cloudflare ne
// peut pas importer de code Python, donc cette liste doit être tenue à jour
// manuellement à chaque changement côté Python (et redéployée : `wrangler
// deploy`). Un déséquilibre ici filtre silencieusement les quartiers absents
// de cette copie (bug vécu le 2026-08-07 : "Cornavin" coché sur le
// formulaire mais retiré silencieusement avant même d'atteindre l'issue
// GitHub).
const DISTRICTS = [
  "Champel", "Eaux-Vives", "Rive", "Rives", "Plainpalais", "Jonction", "Carouge", "Acacias",
  "Cornavin", "Pâquis", "Servette", "Grottes", "Petit-Saconnex", "Charmilles",
];

// Copie obligatoire de utils/parser.py::PROPERTY_TYPES — même remarque que
// DISTRICTS ci-dessus : à tenir à jour manuellement + redéployer.
const PROPERTY_TYPES = ["Dépôt", "Arcade", "Atelier", "Industriel", "Bureau", "Local commercial"];

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function jsonResponse(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "*";

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(origin) });
    }
    if (request.method !== "POST") {
      return jsonResponse({ ok: false, error: "Method not allowed" }, 405, origin);
    }

    let payload;
    try {
      payload = await request.json();
    } catch {
      return jsonResponse({ ok: false, error: "Invalid JSON" }, 400, origin);
    }

    if (!env.EXPECTED_KEY || payload.key !== env.EXPECTED_KEY) {
      return jsonResponse({ ok: false, error: "Accès refusé" }, 403, origin);
    }

    const surface = Number(payload.min_surface_m2);
    const rent = Number(payload.max_rent_chf_month);
    const districts = Array.isArray(payload.allowed_districts)
      ? payload.allowed_districts.filter((d) => DISTRICTS.includes(d))
      : [];
    const propertyTypes = Array.isArray(payload.allowed_property_types)
      ? payload.allowed_property_types.filter((t) => PROPERTY_TYPES.includes(t))
      : [];
    const changingRoom = payload.require_possible_changing_rooms === true;
    const scanHour = Number(payload.scan_hour_geneva);

    if (!Number.isFinite(surface) || surface < 1 || surface > 5000) {
      return jsonResponse({ ok: false, error: "Surface invalide" }, 400, origin);
    }
    if (!Number.isFinite(rent) || rent < 1 || rent > 100000) {
      return jsonResponse({ ok: false, error: "Loyer invalide" }, 400, origin);
    }
    if (!Number.isInteger(scanHour) || scanHour < 0 || scanHour > 23) {
      return jsonResponse({ ok: false, error: "Heure de scan invalide" }, 400, origin);
    }
    if (districts.length === 0) {
      return jsonResponse({ ok: false, error: "Sélectionne au moins un quartier" }, 400, origin);
    }
    if (propertyTypes.length === 0) {
      return jsonResponse({ ok: false, error: "Sélectionne au moins un type de bien" }, 400, origin);
    }

    const body = [
      "Demande de modification des critères envoyée depuis docs/criteria.html.",
      "",
      `surface_min: ${surface}`,
      `loyer_max: ${rent}`,
      `quartiers: ${districts.join(", ")}`,
      `types: ${propertyTypes.join(", ")}`,
      `vestiaires_requis: ${changingRoom ? "oui" : "non"}`,
      `heure_scan: ${scanHour}`,
    ].join("\n");

    const ghResponse = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/issues`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "boxing-gym-scanner-criteria-worker",
      },
      body: JSON.stringify({
        title: "[criteria-update] Nouveaux critères de recherche",
        body,
      }),
    });

    if (!ghResponse.ok) {
      const detail = await ghResponse.text();
      return jsonResponse({ ok: false, error: `GitHub API error: ${ghResponse.status} ${detail}` }, 502, origin);
    }

    const issue = await ghResponse.json();
    return jsonResponse({ ok: true, issue_url: issue.html_url }, 200, origin);
  },
};
