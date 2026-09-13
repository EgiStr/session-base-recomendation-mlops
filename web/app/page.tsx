/* Hallmark · macrostructure: Workbench · tone: playful-profesional cerdas · anchor hue: 252 Signal Blue
 * Shop workbench: katalog kiri (tap → event), rekomendasi live kanan. Mobile-first, bottom tab offset.
 * pre-emit critique: P5 H5 E4 S5 R5 V5
 */
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ProductCard, { type Product } from "../components/ProductCard";
import TabBar from "../components/TabBar";
import {
  getCatalog,
  getSession,
  postEvent,
  type RecoItem,
} from "../lib/api";

const SID_KEY = "tripranker:sid";

/**
 * Verified-real item IDs used only when GET /v1/catalog is unavailable.
 * First 5 = postgres top-5 by views (real popularity ranks 1–5, honest
 * "populer #rank" labels). Rest = pre-existing real-looking catalog IDs
 * (rank unknown → no rank label, never invented).
 * RetailRocket carries no titles/prices — labels stay as "Produk {id}".
 */
const VERIFIED_REAL: Product[] = [
  { item_id: "187946", popularityRank: 1 },
  { item_id: "461686", popularityRank: 2 },
  { item_id: "5411", popularityRank: 3 },
  { item_id: "370653", popularityRank: 4 },
  { item_id: "219512", popularityRank: 5 },
  { item_id: "213834" },
  { item_id: "321422" },
  { item_id: "456881" },
];

function getSid(): string {
  let sid = localStorage.getItem(SID_KEY);
  if (!sid) {
    sid = `shop-${Math.random().toString(36).slice(2, 8)}`;
    localStorage.setItem(SID_KEY, sid);
  }
  return sid;
}

export default function ShopPage() {
  const [sid, setSid] = useState("");
  const [recos, setRecos] = useState<RecoItem[]>([]);
  const [recent, setRecent] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<Product[]>(VERIFIED_REAL);
  const [catalogLive, setCatalogLive] = useState(false);
  const [meta, setMeta] = useState({ version: "—", ms: 0, req: "—" });
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async (id: string) => {
    try {
      const s = await getSession(id, 10);
      setRecos(s.items);
      setRecent(s.recent_items);
      setMeta({ version: s.model_version, ms: s.latency_ms, req: s.request_id });
      setError("");
    } catch {
      setError("API belum hidup — jalankan docker compose up.");
    }
  }, []);

  useEffect(() => {
    const id = getSid();
    setSid(id);
    void refresh(id);
    // Live catalog; falls back to VERIFIED_REAL when /v1/catalog 404s.
    (async () => {
      try {
        const c = await getCatalog(12);
        setCatalog(
          c.items.map((it) => ({
            item_id: it.item_id,
            ...(typeof it.rank === "number"
              ? { popularityRank: it.rank }
              : {}),
            ...(typeof it.views === "number" ? { views: it.views } : {}),
          }))
        );
        setCatalogLive(true);
      } catch {
        setCatalog(VERIFIED_REAL);
        setCatalogLive(false);
      }
    })();
  }, [refresh]);

  const fire = useCallback(
    async (itemId: string, type: "click" | "cart" | "order") => {
      setPending(itemId + type);
      try {
        const out = await postEvent(sid, itemId, type, 10);
        setRecos(out.items);
        setRecent(out.recent_items);
        setMeta({ version: out.model_version, ms: out.latency_ms, req: out.request_id });
        setError("");
      } catch {
        setError("Gagal kirim event — cek koneksi API.");
      } finally {
        setPending(null);
      }
    },
    [sid]
  );

  const counts = useMemo(
    () => ({ klik: recent.length, reco: recos.length }),
    [recent, recos]
  );

  return (
    <div className="mx-auto w-full max-w-lg px-4 pb-24 pt-4">
      <header className="rounded-brand bg-primary-700 p-4 text-white">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary-200">
          TripRanker · simulasi live
        </p>
        <h1 className="font-display text-xl font-bold leading-tight">
          Belanja, kami yang menebak.
        </h1>
        <p className="mt-1 text-sm text-primary-100">
          Ketuk produk — ranker LightGBM (NDCG@10 0.978) menata ulang rekomendasi
          tiap event. Sesi {sid || "…"} · {counts.klik} klik.
        </p>
        <p className="mt-2 font-mono text-[11px] text-primary-200">
          {meta.version} · {meta.ms}ms · {meta.req}
        </p>
      </header>

      {error && (
        <p role="alert" className="mt-3 rounded-brand bg-error-100 p-3 text-sm text-error-700">
          {error}
        </p>
      )}

      <section aria-label="Rekomendasi untukmu" className="mt-5">
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="font-display text-md font-bold text-neutral-900">
            Rekomendasi untukmu
          </h2>
          <span className="rounded-full bg-success-100 px-2 py-0.5 text-xs font-semibold text-success-700">
            live
          </span>
        </div>
        {recos.length === 0 ? (
          <p className="rounded-brand border border-dashed border-neutral-300 p-4 text-sm text-neutral-500">
            Belum ada klik di sesi ini. Ketuk produk di bawah untuk mulai.
          </p>
        ) : (
          <ol className="grid grid-cols-2 gap-2.5">
            {recos.map((r, i) => (
              <li key={r.item_id}>
                <ProductCard
                  product={{ item_id: r.item_id, score: r.score, rank: i + 1 }}
                  onClick={() => void fire(r.item_id, "click")}
                  onCart={() => void fire(r.item_id, "cart")}
                  onOrder={() => void fire(r.item_id, "order")}
                  pending={pending !== null}
                />
              </li>
            ))}
          </ol>
        )}
      </section>

      <section aria-label="Katalog" className="mt-6">
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="font-display text-md font-bold text-neutral-900">
            Katalog populer
          </h2>
          <span className="rounded-full bg-primary-100 px-2 py-0.5 text-xs font-semibold text-primary-700">
            {catalogLive ? "live" : "populer"}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2.5">
          {catalog.map((p) => (
            <ProductCard
              key={p.item_id}
              product={p}
              onClick={() => void fire(p.item_id, "click")}
              onCart={() => void fire(p.item_id, "cart")}
              onOrder={() => void fire(p.item_id, "order")}
              pending={pending !== null}
            />
          ))}
        </div>
      </section>

      {recent.length > 0 && (
        <section aria-label="Riwayat sesi" className="mt-6">
          <h2 className="mb-2 font-display text-md font-bold text-neutral-900">
            Jejak sesi ({recent.length})
          </h2>
          <div className="flex flex-wrap gap-1.5">
            {recent.slice(-12).map((id, i) => (
              <span
                key={`${id}-${i}`}
                className="rounded-full bg-primary-100 px-2.5 py-1 text-xs font-semibold text-primary-700"
              >
                {id}
              </span>
            ))}
          </div>
        </section>
      )}
      <TabBar />
    </div>
  );
}
