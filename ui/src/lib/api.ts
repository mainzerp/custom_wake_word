import type { Counts, Label, Session, SplitParams } from "./types";

type SessionResult = { session: Session; counts: Counts };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.detail || res.statusText);
  return data as T;
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

const base = "/api/studio";

export const studio = {
  sessions: () => request<{ sessions: Session[]; counts: Counts }>(`${base}/sessions`),
  upload: (wav: Blob, params: SplitParams, prefix: string) =>
    request<SessionResult>(`${base}/upload`, {
      method: "POST",
      headers: { "Content-Type": "audio/wav", "X-Split-Params": JSON.stringify(params), "X-Prefix": encodeURIComponent(prefix) },
      body: wav,
    }),
  split: (session: string, params: SplitParams) => post<SessionResult>(`${base}/split`, { session, params }),
  rename: (session: string, prefix: string) => post<SessionResult>(`${base}/rename`, { session, prefix }),
  label: (session: string, clips: string[], label: Label | null) => post<SessionResult>(`${base}/label`, { session, clips, label }),
  labelUnsorted: (session: string, label: Label) => post<SessionResult>(`${base}/label_unsorted`, { session, label }),
  deleteClip: (session: string, clip: string) => post<SessionResult>(`${base}/delete_clip`, { session, clip }),
  deleteSession: (session: string) => post<{ ok: boolean; counts: Counts }>(`${base}/delete_session`, { session }),
  recordingUrl: (session: string) => `${base}/files/${session}/recording.wav`,
  clipUrl: (session: string, clip: string) => `${base}/files/${session}/clips/${encodeURIComponent(clip)}`,
};
