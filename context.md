# context.md

Business/project context for the Boxing Gym Scanner. This is the "why"
behind the project — CLAUDE.md covers the technical architecture, this file
covers the people, goals, and decisions that shaped it.

## Who this is for

The scanner exists to help the user's father find a commercial premises in
Geneva to rent for his boxing gym business. The father is the actual
end-user of the results (via email/Telegram) but is not technical — he
doesn't have a GitHub account and isn't expected to get one. Any feature
aimed at him (viewing listings, editing search criteria) has to work from a
link he can click, with no login, no CLI, no YAML editing.

The user (Flavius) owns the GitHub repo, the automation, and the code. He's
the one who reads CLAUDE.md and does the engineering; his father only ever
sees the website and the notifications.

## Why the project is shaped the way it is

- **Zero ongoing cost.** GitHub Actions (free tier) is the only compute.
  No paid hosting, no server to maintain — this was a deliberate constraint
  from the start, not an oversight. Any new feature should default to
  staying inside that constraint (GitHub Pages, GitHub Issues, Cloudflare
  Workers free tier are fine; a paid backend is not).
- **The repo was private until 2026-08-07**, when it was made public
  specifically so GitHub Pages could serve `docs/index.html` at a stable,
  public URL that could be linked from emails and Telegram messages (see
  [[criteria-edit-flow]]). Before that, the generated site was only
  reachable as an email attachment.
- **Father-editable criteria.** As of 2026-08-07 the father can change the
  search criteria (surface, rent ceiling, districts, property type) himself
  from a page on the public site, without a GitHub account — see
  [[criteria-edit-flow]] for how that's wired end to end (Cloudflare Worker
  → GitHub Issue → GitHub Action → `config.yaml`). This was a deliberate
  choice over having Flavius manually update `config.yaml` every time the
  father wants to adjust criteria. Fully deployed and confirmed working
  with real submissions from the father the same day (not just Claude's
  test traffic) — see [[criteria-edit-flow]] for the live values that
  resulted (loyer max 2'501 CHF, surface min 30 m², all 14 districts).
- **Checkbox semantics matter to this user.** The property-type filter
  originally treated "no boxes checked" as "accept every type" (to avoid
  breaking existing coverage by default). The father flagged this as
  backwards the same day he started using the form — he expected unchecked
  = excluded, like every other checkbox UI. Flipped to match
  `allowed_districts` (must check at least one). Worth remembering when
  designing any future checkbox-based filter here: default to conventional
  checkbox semantics, don't get clever with "empty = permissive" without
  checking with him first.

## Related memory

- [[criteria-edit-flow]] — architecture, deployment status (live), and the
  bugs found/fixed while shipping it — useful before touching that flow
  again.
