/* Hallmark · macrostructure: Workbench · tone: playful-profesional cerdas · anchor hue: 252 Signal Blue + 38 Cart Ember accent */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type RecoItem = { item_id: string; score: number };

export type EventOut = {
  request_id: string;
  session_id: string;
  model_version: string;
  latency_ms: number;
  items: RecoItem[];
  recent_items: string[];
  reason?: string | null;
};

export type SessionOut = EventOut & { last_event?: string | null };

export async function postEvent(
  sessionId: string,
  itemId: string,
  eventType: "click" | "cart" | "order" = "click",
  k = 10
): Promise<EventOut> {
  const r = await fetch(`${API_BASE}/v1/events`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      item_id: itemId,
      event_type: eventType,
      track: "retailrocket",
      k,
    }),
  });
  if (!r.ok) throw new Error(`events ${r.status}`);
  return (await r.json()) as EventOut;
}

export async function getSession(
  sessionId: string,
  k = 10
): Promise<SessionOut> {
  const r = await fetch(
    `${API_BASE}/v1/session/${encodeURIComponent(sessionId)}?track=retailrocket&k=${k}`
  );
  if (!r.ok) throw new Error(`session ${r.status}`);
  return (await r.json()) as SessionOut;
}

export async function getHealth(): Promise<{ status: string; ready: boolean }> {
  const h = (await fetch(`${API_BASE}/health`).then((r) =>
    r.json()
  )) as { status: string };
  let ready = false;
  try {
    const rd = await fetch(`${API_BASE}/ready`);
    ready = rd.ok;
  } catch {
    ready = false;
  }
  return { status: h.status, ready };
}

export async function getP95(): Promise<{ p95_ms: number; samples: number }> {
  // JSON endpoint first; the raw Prometheus text lives at /metrics.
  try {
    const r = await fetch(`${API_BASE}/metrics/json`);
    if (!r.ok) throw new Error(`metrics/json ${r.status}`);
    return (await r.json()) as { p95_ms: number; samples: number };
  } catch {
    const r = await fetch(`${API_BASE}/metrics`);
    if (!r.ok) throw new Error(`metrics ${r.status}`);
    return (await r.json()) as { p95_ms: number; samples: number };
  }
}

export type CatalogItem = { item_id: string; rank?: number; views?: number };
export type CatalogOut = { items: CatalogItem[] };

/** Thrown when GET /v1/catalog is unavailable (e.g. endpoint not yet added). */
export class CatalogUnavailableError extends Error {
  constructor(message = "catalog unavailable") {
    super(message);
    this.name = "CatalogUnavailableError";
  }
}

/**
 * Live catalog from the API: GET /v1/catalog?n=12 → {"items":[{"item_id","rank"}]}.
 * Throws CatalogUnavailableError when the endpoint is missing/failing so the
 * page can fall back to the verified-real ID list.
 */
export async function getCatalog(n = 12): Promise<CatalogOut> {
  let r: Response;
  try {
    r = await fetch(`${API_BASE}/v1/catalog?n=${n}`);
  } catch (e) {
    throw new CatalogUnavailableError(
      e instanceof Error ? e.message : "catalog fetch failed"
    );
  }
  if (!r.ok) throw new CatalogUnavailableError(`catalog ${r.status}`);
  const raw = (await r.json()) as {
    items?: Array<{ item_id?: string | number; rank?: number; views?: number }>;
  };
  const items: CatalogItem[] = Array.isArray(raw.items)
    ? raw.items
        .filter((it) => it && it.item_id !== undefined && it.item_id !== null)
        .map((it) => ({
          item_id: String(it.item_id),
          ...(typeof it.rank === "number" ? { rank: it.rank } : {}),
          ...(typeof it.views === "number" ? { views: it.views } : {}),
        }))
    : [];
  if (items.length === 0) throw new CatalogUnavailableError("catalog empty");
  return { items };
}
