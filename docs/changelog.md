# Changelog

> Release history from git (`git log --oneline`). Newest first.
> Only shipped commits; each entry states what changed and why.

- `64450b6` **fix(web): reco cards carry stats + category** — reco grid
  previously passed only id/score; now forwards all enrichment fields.
- `02e7f3f` **feat(web): rich honest cards + session audit panel** — visual
  ID fingerprints, real-stats cards, category chips, A-vs-B audit tool.
- `dbe2946` **fix(api): RecoItem carries category + rank fields** — Pydantic
  response model was stripping the enriched fields; root-caused via live probe.
- `78dcf15` **feat(catalog): real category chips + A-vs-B compare endpoint**
  — `item_category` table (417k items / 1,180 cats), `GET /v1/compare`.
- `6396724` **ops(docker): full-docker wiring** — `api` service + Prometheus
  scrape in compose; 9 services live.
- `7e4f5ff` **docs(ops): local-dev wiring glue + alignment evidence record**.
- `6b94c4e` **test(api): catalog, stats-absent, sink, monitor coverage**.
- `4fb983c` **feat(retrain): docker-mlflow retrain + registry champion +
  app-events cycle** — closed MLOps loop.
- `23e0b67` **fix(wiring): dual-listener kafka** — host + compose both reachable.
- `1755131` **feat(web): real catalog + order action + grafana provisioning**.
- `9ab7ba3` **fix(wiring): redis sessions + prometheus metrics + catalog +
  streaming consumer**.
- `067dc35` **docs(evidence): browser live proof + cors + popularity fixes**.
- `e620733` **fix(api): cold-start serves true popularity order** via
  `ranker.popularity()` (inventory.csv ascending ≠ popularity order).
- `ac2433f` **perf(api): candidate funnel 500 + session context to ranker** —
  full-inventory scoring (~1.1 s) → P95 ≈ 2.7 ms.
- `2440000` **feat(deploy): web service in compose + dockerfile** — full stack live-proofed.

Earlier history (scaffold, brand, training, postgres reproduction) precedes
`2440000` — see `git log` for the full trail.
