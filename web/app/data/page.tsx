/* Hallmark · macrostructure: Long Document · tone: editorial cerdas · anchor hue: 252 Signal Blue
 * Data ledger: reproduksi RetailRocket → Postgres. Differs from Workbench + Stat-Led on structure.
 * pre-emit critique: P5 H5 E5 S5 R5 V5
 */
import TabBar from "../../components/TabBar";

const STEPS = [
  {
    t: "1 · Unduh (auth-free)",
    d: "HuggingFace DanielKiani/RetailRocket-Recommender-Data → data/raw_hf. 2.756.101 baris, kolom timestamp, visitorid, event, itemid, transactionid.",
  },
  {
    t: "2 · COPY streaming ke Postgres",
    d: "scripts/db/load_retailrocket.py — COPY events_raw FROM STDIN per chunk 200rb baris, 20 detik total. CSV read-only, tak digandakan di disk hemat 14GB.",
  },
  {
    t: "3 · Agregat sql/02_aggregates.sql",
    d: "sessions (1.407.580 baris: sess_len, last_ts, recent_items[20]) + item_stats (235.061 baris: views, carts, orders, item_pop, item_conv_rate) — umpan fitur ranker.",
  },
  {
    t: "4 · Latih + bake",
    d: "LightGBM lambdarank, holdout 7 hari. NDCG@10 0.978 vs baseline 0.727. Artefak di artifacts/ranker-retailrocket-v1, di-bake ke image API.",
  },
];

const DIST = [
  { e: "view → click", n: "2.664.312", pct: 96.7 },
  { e: "addtocart → cart", n: "69.332", pct: 2.5 },
  { e: "transaction → order", n: "22.457", pct: 0.8 },
];

export default function DataPage() {
  return (
    <div className="mx-auto w-full max-w-lg px-4 pb-24 pt-4">
      <p className="text-xs font-semibold uppercase tracking-widest text-primary-600">
        TripRanker · Data
      </p>
      <h1 className="font-display text-xl font-bold leading-tight text-neutral-900">
        Dari 2,7 juta event nyata ke rekomendasi.
      </h1>
      <p className="mt-1 text-sm text-neutral-500">
        Seluruh dataset RetailRocket direproduksi di PostgreSQL lokal — bukan
        CSV tempel, bukan angka mock.
      </p>

      <div className="mt-4 grid grid-cols-3 gap-2.5 text-center">
        {[
          ["2.756.101", "event"],
          ["1.407.580", "sesi"],
          ["235.061", "produk"],
        ].map(([v, l]) => (
          <div key={l} className="rounded-brand bg-primary-700 p-3 text-white">
            <p className="font-display text-md font-bold">{v}</p>
            <p className="text-xs text-primary-200">{l}</p>
          </div>
        ))}
      </div>

      <h2 className="mb-2 mt-6 font-display text-md font-bold text-neutral-900">
        Distribusi event → label
      </h2>
      <div className="space-y-2">
        {DIST.map((d) => (
          <div key={d.e} className="rounded-brand border border-neutral-200 bg-white p-3">
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-sm font-bold text-neutral-900">{d.e}</p>
              <p className="font-mono text-xs text-neutral-500">{d.n}</p>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-neutral-200">
              <div
                className="h-full rounded-full bg-accent-500"
                style={{ width: `${Math.max(2, d.pct)}%` }}
                role="img"
                aria-label={`${d.e} ${d.pct} persen`}
              />
            </div>
          </div>
        ))}
      </div>

      <h2 className="mb-2 mt-6 font-display text-md font-bold text-neutral-900">
        Cara mereproduksi
      </h2>
      <ol className="space-y-2.5">
        {STEPS.map((s) => (
          <li key={s.t} className="rounded-brand border border-neutral-200 bg-white p-3">
            <p className="text-sm font-bold text-primary-700">{s.t}</p>
            <p className="mt-0.5 font-mono text-xs leading-relaxed text-neutral-600">
              {s.d}
            </p>
          </li>
        ))}
      </ol>

      <div className="mt-4 rounded-brand bg-neutral-900 p-3 font-mono text-xs leading-relaxed text-neutral-100">
        <p>$ docker compose up -d postgres</p>
        <p>$ python scripts/db/load_retailrocket.py</p>
        <p className="text-neutral-400"># + sql/02_aggregates.sql via psycopg</p>
      </div>
      <TabBar />
    </div>
  );
}
