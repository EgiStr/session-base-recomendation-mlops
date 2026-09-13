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
  return r.json();
}

export async function getSession(
  sessionId: string,
  k = 10
): Promise<SessionOut> {
  const r = await fetch(
    `${API_BASE}/v1/session/${encodeURIComponent(sessionId)}?track=retailrocket&k=${k}`
  );
  if (!r.ok) throw new Error(`session ${r.status}`);
  return r.json();
}

export async function getHealth(): Promise<{
  status: string;
  ready?: boolean;
  model_version?: string;
}> {
  const h = await fetch(`${API_BASE}/health`).then((r) => r.json());
  const rd = await fetch(`${API_BASE}/ready`)
    .then((r) => ({ ok: r.ok, body: r.json() } as never))
    .catch(() => null);
  return { status: h.status, ready: !!(rd as { ok: boolean } | null)?.ok };
}
