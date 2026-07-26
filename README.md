# Geneva Gym Scanner

Scanner gratuit hébergé sur GitHub Actions pour repérer des locaux commerciaux à louer à Genève pouvant convenir à une salle de sport.

## Fonctionnalités
- scrape plusieurs sites immobiliers (realadvisor.ch, rosset.ch, pilet-renaud.ch, immobilier.ch, acheter-louer.ch, naef.ch)
- filtre selon surface, loyer, quartier, vestiaires potentiels
- stocke l'historique dans SQLite
- exporte Excel et CSV
- détecte nouvelles annonces / annonces modifiées / annonces supprimées
- notifications Telegram et email
- exécution automatique toutes les 3 heures via GitHub Actions
- dashboard Streamlit local
- **site web statique** (`docs/index.html`) listant toutes les annonces et
  celles qui correspondent aux critères, avec lien direct vers chaque
  annonce — généré à chaque run, publiable gratuitement via GitHub Pages

## Publier le site de résultats (GitHub Pages, gratuit)
Une fois le dépôt poussé sur GitHub, à faire une seule fois :
1. Settings → Pages
2. Source : "Deploy from a branch"
3. Branch : `main`, dossier `/docs`
4. Enregistrer

Le site sera disponible à `https://<votre-compte>.github.io/<nom-du-repo>/`
et se mettra à jour tout seul à chaque exécution du scanner (le workflow
commite `docs/index.html` avec le reste des données).

## Sites non couverts
- **homegate.ch, comparis.ch** (et par extension immoscout24.ch,
  properstar.com, anibis.ch) : protection anti-bot active (Cloudflare
  "Just a moment...", CAPTCHA DataDome, page de sécurité), y compris avec un
  vrai navigateur headless. Contourner ce type de protection n'est pas fait
  ici. Créez plutôt une alerte email native depuis leur recherche (icône
  cloche / "créer une alerte") avec les mêmes critères : vous recevrez les
  nouvelles annonces aussi vite, sans contournement.
- **spg.ch** : moteur de recherche chargé en JS depuis un widget externe
  (+ reCAPTCHA), pas de contenu statique exploitable simplement.
- **wincasa.ch** : même situation, widget de recherche externe.
- **urbanhome.ch** : quasiment aucune offre commerciale (portail surtout
  résidentiel), pas assez de volume pour justifier un scraper dédié.

## Lancement local
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python main.py
```

## Dashboard local
```bash
streamlit run dashboard/app.py
```

## Secrets GitHub à créer
- TELEGRAM_TOKEN
- TELEGRAM_CHAT_ID
- EMAIL_HOST
- EMAIL_PORT
- EMAIL_USERNAME
- EMAIL_PASSWORD
- EMAIL_TO
