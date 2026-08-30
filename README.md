# Geneva Gym Scanner

Scanner gratuit hébergé sur GitHub Actions pour repérer des locaux commerciaux à louer à Genève pouvant convenir à une salle de sport.

## Fonctionnalités
- scrape plusieurs sites immobiliers (realadvisor.ch, rosset.ch, pilet-renaud.ch,
  immobilier.ch, acheter-louer.ch, naef.ch, moservernet.ch, netimmo.ch), avec
  une couverture explicite des arcades ET des dépôts (naef, moservernet,
  pilet-renaud ont chacun une catégorie dépôt séparée en plus de leur
  catégorie commerciale/bureaux)
- filtre selon surface, loyer, quartier, vestiaires potentiels
- stocke l'historique dans SQLite
- exporte Excel et CSV
- détecte nouvelles annonces / annonces modifiées / annonces supprimées
  (toujours suivies en base et sur le site, même sans notification)
- notifications Telegram et email — déclenchées uniquement par de
  nouvelles annonces (une annonce modifiée seule, sans nouveauté, ne
  notifie plus rien depuis le passage au scan quotidien)
- exécution automatique une fois par jour via GitHub Actions (heure
  modifiable depuis le site, voir "Modifier les critères depuis le site")
- dashboard Streamlit local
- **site web statique** (`docs/index.html`) listant toutes les annonces et
  celles qui correspondent aux critères, avec lien direct vers chaque
  annonce — généré à chaque run, publié gratuitement via GitHub Pages à
  <https://flaviusmeding.github.io/Boxing-Gym-Scanner/>, et lié depuis les
  notifications Telegram/email
- **modification des critères depuis le site** (`docs/criteria.html`), sans
  compte GitHub — voir "Modifier les critères depuis le site" ci-dessous

## Site de résultats (GitHub Pages, gratuit)
Le dépôt est public et GitHub Pages est activé (Settings → Pages, source
`main` / dossier `/docs`) — c'était une condition nécessaire pour que le
site soit accessible depuis un lien dans les emails/Telegram (avant, il
n'était que joint en pièce jointe à l'email). Le site se met à jour tout
seul à chaque exécution du scanner : le workflow commite `docs/index.html`
avec le reste des données.

URL : <https://flaviusmeding.github.io/Boxing-Gym-Scanner/>

## Modifier les critères depuis le site
`docs/criteria.html` permet de changer la surface minimum, le loyer
maximum, les quartiers acceptés, le(s) type(s) de bien (Dépôt, Arcade,
Atelier, Industriel, Bureau, Local commercial), l'exigence de vestiaires,
et l'heure du scan quotidien, sans compte GitHub ni édition manuelle de
`config.yaml`/`scanner.yml`. Comme pour les quartiers, seuls les types
cochés sont acceptés (il faut en cocher au moins un). Le lien (avec la clé
d'accès) est ajouté automatiquement à la fin de chaque notification
Telegram/email.

Flux complet :
1. La page envoie le formulaire à un **Cloudflare Worker** (`worker/`).
2. Le Worker vérifie la clé d'accès, puis crée une **issue GitHub** avec les
   valeurs demandées (le Worker est le seul endroit qui détient un token
   GitHub capable d'écrire sur le repo — jamais exposé côté client).
3. La GitHub Action `.github/workflows/apply-criteria.yml` lit l'issue,
   met à jour `config.yaml` et, si l'heure du scan a changé, le cron dans
   `.github/workflows/scanner.yml` (`scripts/apply_criteria_update.py`),
   commite, puis ferme l'issue avec un message de confirmation.
4. Le prochain scan (le lendemain à l'heure configurée, au plus tard) utilise
   les nouveaux critères.

**État actuel : déployé et fonctionnel** (Worker live à
`https://boxing-gym-criteria.boxinggym-tracker.workers.dev`, `config.yaml`
→ `output.criteria_worker_url` déjà renseigné, testé de bout en bout avec
de vraies soumissions). Les étapes ci-dessous ne sont utiles que pour
redéployer ailleurs ou en cas de recréation du Worker :
1. Créer un compte Cloudflare gratuit (workers.dev) si besoin.
2. Créer un **PAT GitHub fine-grained** (Settings → Developer settings →
   Fine-grained tokens) limité à ce repo, permission **Issues: Read and
   write** uniquement — pas plus.
3. Depuis `worker/` : `npx wrangler login`, puis
   `npx wrangler secret put GITHUB_TOKEN` (coller le PAT) et
   `npx wrangler secret put EXPECTED_KEY` (coller la valeur du secret
   GitHub `CRITERIA_EDIT_TOKEN`, voir section secrets ci-dessous).
4. `npx wrangler deploy` → note l'URL `https://boxing-gym-criteria.<ton-compte>.workers.dev`.
   Sous Windows/PowerShell, si `npx` est bloqué par la politique
   d'exécution de scripts (`... est désactivée sur ce système`), utiliser
   `npx.cmd` à la place — ce n'est pas concerné par cette restriction.
5. Mettre cette URL dans `config.yaml` → `output.criteria_worker_url`,
   commit/push. Elle sera embarquée dans `docs/criteria.html` au prochain
   run.

## Sites non couverts
- **homegate.ch, comparis.ch, newhome.ch** (et par extension
  immoscout24.ch, properstar.com, anibis.ch) : protection anti-bot active
  (Cloudflare "Just a moment...", CAPTCHA DataDome, page de sécurité), y
  compris avec un vrai navigateur headless. Contourner ce type de
  protection n'est pas fait ici. Créez plutôt une alerte email native
  depuis leur recherche (icône cloche / "créer une alerte") avec les mêmes
  critères : vous recevrez les nouvelles annonces aussi vite, sans
  contournement.
- **spg.ch** : moteur de recherche chargé en JS depuis un widget externe
  (+ reCAPTCHA), pas de contenu statique exploitable simplement.
- **wincasa.ch** : même situation, widget de recherche externe.
- **urbanhome.ch** : quasiment aucune offre commerciale (portail surtout
  résidentiel), pas assez de volume pour justifier un scraper dédié.
- **regiefonciere.ch** (Régie Foncière SA) : pas de scraper dédié — ses
  annonces sont déjà republiées sur immobilier.ch, qui est déjà couvert.
- **immostreet.ch** : appartient au même groupe (Swiss Marketplace Group)
  que homegate.ch/immoscout24.ch, donc probablement protégé par le même
  système anti-bot — pas testé individuellement, écarté par précaution pour
  la même raison.
- **immoadvisor.com** : candidat identifié (2026-08-07), contenu réel
  détecté (777 mentions "CHF" sur la page de résultats Genève, statut 200),
  mais pas encore de sélecteur CSS validé — à investiguer si plus de
  couverture est souhaitée.
- **Gérance Immobilière Municipale (geneve.ch)** : la Ville de Genève loue
  elle-même bureaux/arcades/dépôts/ateliers, liste publiée en PDF (pas en
  HTML scrapable directement) et via un processus de candidature/dépôt de
  garantie de 6 mois plutôt qu'un contact direct régie — nécessiterait un
  scraper différent (parsing PDF) et un flux différent pour l'utilisateur.
  Non implémenté, mentionné ici comme piste.

**netimmo.ch, une réserve :** son CDN d'images (`img.realadvisor.ch`)
suggère qu'il republie les mêmes données que realadvisor.ch (déjà scrapé) —
attendez-vous à des doublons entre les deux sources dans les résultats.
Gardé actif quand même car demandé explicitement ; à désactiver
(`sites.netimmo.enabled: false`) si les doublons gênent plus qu'ils
n'aident.

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
- CRITERIA_EDIT_TOKEN — clé d'accès à `docs/criteria.html`, embarquée dans le
  lien des notifications ; doit avoir la même valeur que le secret
  `EXPECTED_KEY` du Cloudflare Worker (voir "Modifier les critères depuis
  le site")
- WORKFLOW_EDIT_TOKEN — PAT fine-grained (permissions **Contents: Read and
  write** + **Workflows: Read and write**, limité à ce repo, **No
  expiration**), configuré (2026-08-30). Nécessaire uniquement parce que
  `GITHUB_TOKEN` ne peut jamais pousser de changement sous
  `.github/workflows/` (restriction GitHub non contournable via
  `permissions:` — confirmé en cassant tout le workflow en essayant) ; sans
  lui, le champ "Heure du scan" de `docs/criteria.html` mettrait à jour
  `config.yaml` mais pas le cron réel dans `scanner.yml`. Les PAT
  fine-grained expirent par défaut sur une courte durée si "No expiration"
  n'est pas explicitement choisi à la création — **CRITERIA_EDIT_TOKEN a
  déjà expiré une fois** (le formulaire de critères a été cassé silencieusement
  pendant plusieurs jours avant d'être détecté) ; vérifier régulièrement
  que `wrangler secret list` / ce secret sont toujours valides, ou
  régénérer en cas de doute plutôt que d'attendre un échec.
