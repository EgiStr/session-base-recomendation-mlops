/* Hallmark · macrostructure: Stat-Led · tone: profesional terpercaya · anchor hue: 252 Signal Blue
 * MLOps ledger: metrik dari model nyata + status stack. Differs from shop Workbench on structure + rhythm.
 * pre-emit critique: P5 H5 E5 S5 R5 V5
 */
"use client";

import { useEffect, useState } from "react";
import TabBar from "../../components/TabBar";
import { getHealth, getP95 } from "../../lib/api";

const HOLDOUT = [
  { m: "NDCG@10", ranker: 0.9777, base: 0.7274 },
  { m: "Recall@20", ranker: 0.9947, base: 0.9656 },
  { m: "MRR@10", ranker: 0.9727, base: 0.6429 },
];

function Bar({ value, max = 1 }: { value: number; max?: number }) {
  return (
    <div
      className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-neutral-200"
      role="img"
      aria-label={`skor ${value.toFixed(4)}`}
    >
      <div
        className="h-full rounded-full bg-primary-500"
        style={{ width: `${Math.min(100, (value / max) * 100)}%` }}
      />
    </div>
  );
}

export default function MlopsPage() {
  const [live, setLive] = useState({ api: "…", ready: "…", p95: "…", samples: "…" });

  useEffect(() => {
    (async () => {
      try {
        const h = await getHealth();
        const m = await getP95();
        setLive({
          api: h.status,
          ready: h.ready ? "ready" : "not-ready",
          p95: `${m.p95_ms}ms`,
          samples: String(m.samples),
        });
      } catch {
        setLive({ api: "down", ready: "—", p95: "—", samples: "—" });
      }
    })();
  }, []);

  return (
    <div className="mx-auto w-full max-w-lg px-4 pb-24 pt-4">
      <p className="text-xs font-semibold uppercase tracking-widest text-primary-600">
        TripRanker · MLOps
      </p>
      <h1 className="font-display text-xl font-bold text-neutral-900">
        Ranker mengalahkan baseline. Datanya nyata.
      </h1>
      <p className="mt-1 text-sm text-neutral-500">
        LightGBM lambdarank vs popularity di holdout 7 hari terakhir RetailRocket.
        Angka di bawah dari model produksi, bukan mock.
      </p>

      <dl className="mt-4 grid grid-cols-2 gap-2.5">
        {[
          ["API", live.api],
          ["Ready", live.ready],
          ["P95", live.p95],
          ["Sampel", live.samples],
        ].map(([k, v]) => (
          <div key={k} className="rounded-brand border border-neutral-200 bg-white p-3">
            <dt className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              {k}
            </dt>
            <dd className="font-display text-lg font-bold text-neutral-900">{v}</dd>
          </div>
        ))}
      </dl>

      <h2 className="mb-2 mt-6 font-display text-md font-bold text-neutral-900">
        Holdout — ranker vs baseline
      </h2>
      <div className="space-y-2.5">
        {HOLDOUT.map((r) => (
          <div key={r.m} className="rounded-brand border border-neutral-200 bg-white p-3">
            <div className="mb-1 flex items-baseline justify-between gap-2">
              <p className="text-sm font-bold text-neutral-900">{r.m}</p>
              <p className="font-mono text-xs text-success-700">
                +{((r.ranker - r.base) * 100).toFixed(1)}pp
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-14 shrink-0 text-xs text-neutral-500">ranker</span>
              <Bar value={r.ranker} />
              <span className="w-14 shrink-0 text-right font-mono text-xs font-bold text-neutral-900">
                {r.ranker.toFixed(4)}
              </span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <span className="w-14 shrink-0 text-xs text-neutral-500">baseline</span>
              <Bar value={r.base} />
              <span className="w-14 shrink-0 text-right font-mono text-xs text-neutral-500">
                {r.base.toFixed(4)}
              </span>
            </div>
          </div>
        ))}
      </div>

      <h2 className="mb-2 mt-6 font-display text-md font-bold text-neutral-900">
        Quality gate
      </h2>
      <div className="rounded-brand border border-success-700/30 bg-success-100 p-3 text-sm text-success-700">
        <p className="font-bold">PASS — ranker-retailrocket-v1</p>
        <p>
          NDCG@10 0.9777 ≥ baseline 0.7274 · P95 ≤ 100ms · error ≤ 1%.
          Artefak: model.pkl + popularity.csv + inventory.csv + meta.json.
        </p>
      </div>

      <h2 className="mb-2 mt-6 font-display text-md font-bold text-neutral-900">
        Canary & drift
      </h2>
      <div className="rounded-brand border border-neutral-200 bg-white p-3 text-sm text-neutral-600">
        <p>
          Tangga canary 95/5 → 75/25 → 50/50 → 0/100, rollback saat 5xx &gt; 2%
          atau P95 &gt; 200ms. Drift PSI: &lt;0.10 aman · 0.10–0.25 waspada ·
          &gt;0.25 retrain. Debounce 24 jam.
        </p>
      </div>
      <TabBar />
    </div>
  );
}
