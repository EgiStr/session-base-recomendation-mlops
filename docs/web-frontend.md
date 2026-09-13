# Web Frontend (Next.js)

> Source: `web/` at `64450b6`. Next.js 16, mobile-first, bottom-tab nav.
> Reads live API only — no mocks anywhere (grep-verified zero invented
> names/prices/cities). `API_BASE` from `NEXT_PUBLIC_API_BASE`
> (default `http://localhost:8000`), **baked at build** — rebuild the image
> after changing it.

## Pages

| Route | Structure | Content |
|---|---|---|
| `/` Belanja (shop Workbench) | header session card → reco grid → catalog grid → session trail → **Audit panel** → tabs | `ProductCard` grid (2-col): visual ID fingerprint, `#rank` badge, stats (views, cart/order, conv%), `categoryid` chip + sibling count, honesty caption, `+ Keranjang` / `Beli` actions. Cold start = true popularity (187946 #1). Every tap fires `POST /v1/events` and re-ranks in one round-trip; clicked item returns top-1. |
| `/mlops` | Stat-Led ledger | live API/Ready/P95/samples from `/health`+`/ready`+`/metrics/json`; holdout table ranker-vs-baseline (+25.0pp NDCG, +2.9pp Recall, +33.0pp MRR); quality-gate PASS card; canary + drift bands explainer. |
| `/data` | Long Document | pipeline narrative: dataset → aggregates → training → serving → retrain cycle, with file/SQL refs. |

## Components

- `ProductCard.tsx` — deterministic gradient thumb from `item_id`
  (5-hue palette, same id = same colors) + `#shortId` fingerprint; all
  numeric fields optional-chained (absent stats simply don't render).
- `AuditPanel.tsx` — session trace (session/model/latency/request/last
  event/trail count) + A-vs-B compare via `GET /v1/compare` (defaults
  `187946` vs `461686`); unknown ids render the "tak dikenal" dashed card.
- `TabBar.tsx` — bottom navigation, active-tab highlight.

## Resilience

`getCatalog` throws `CatalogUnavailableError` on any failure → page falls
back to the `VERIFIED_REAL` ID list (top popularity IDs verified against
the CSV). `postEvent`/`getSession` failures surface an inline banner, never
a blank page. `getP95` tries `/metrics/json` then `/metrics`.
