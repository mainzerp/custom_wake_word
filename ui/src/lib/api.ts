import { slug } from "./state.svelte";
import type {
  Counts,
  GenClip,
  GenerateParams,
  GenerateStatus,
  Job,
  Label,
  Project,
  ProjectSettings,
  Session,
  SplitParams,
} from "./types";

type SessionResult = { session: Session; counts: Counts };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.detail || res.statusText);
  return data as T;
}

const send = <T>(method: string, path: string, body: unknown) =>
  request<T>(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const post = <T>(path: string, body: unknown) => send<T>("POST", path, body);

export const projects = {
  list: () => request<{ projects: Project[] }>("/api/projects"),
  get: (slug: string) => request<Project>(`/api/projects/${encodeURIComponent(slug)}`),
  create: (settings: Partial<ProjectSettings>) => post<Project>("/api/projects", settings),
  update: (slug: string, settings: Partial<ProjectSettings>) => send<Project>("PATCH", `/api/projects/${encodeURIComponent(slug)}`, settings),
};

const projectBase = () => `/api/projects/${encodeURIComponent(slug())}`;

export const generate = {
  status: () => request<GenerateStatus>(`${projectBase()}/generate`),
  start: (params: GenerateParams) => post<Job>(`${projectBase()}/generate/start`, params),
  reset: () => post<GenerateStatus>(`${projectBase()}/generate/reset`, {}),
  samples: (n = 12) => request<{ clips: GenClip[] }>(`${projectBase()}/generate/samples?n=${n}`),
};

export const tts = {
  preview: (language: string, phrases: string[], n = 2) =>
    post<{ engine: string; clips: GenClip[] }>("/api/tts/preview", { language, phrases, n }),
};

export const jobs = {
  active: () => request<{ job: Job | null }>("/api/jobs/active"),
  stop: (id: string) => post<Job>(`${projectBase()}/jobs/${id}/stop`, {}),
};

const base = () => `${projectBase()}/studio`;

export const studio = {
  sessions: () => request<{ sessions: Session[]; counts: Counts }>(`${base()}/sessions`),
  upload: (wav: Blob, params: SplitParams, prefix: string) =>
    request<SessionResult>(`${base()}/upload`, {
      method: "POST",
      headers: { "Content-Type": "audio/wav", "X-Split-Params": JSON.stringify(params), "X-Prefix": encodeURIComponent(prefix) },
      body: wav,
    }),
  split: (session: string, params: SplitParams) => post<SessionResult>(`${base()}/split`, { session, params }),
  rename: (session: string, prefix: string) => post<SessionResult>(`${base()}/rename`, { session, prefix }),
  label: (session: string, clips: string[], label: Label | null) => post<SessionResult>(`${base()}/label`, { session, clips, label }),
  labelUnsorted: (session: string, label: Label) => post<SessionResult>(`${base()}/label_unsorted`, { session, label }),
  deleteClip: (session: string, clip: string) => post<SessionResult>(`${base()}/delete_clip`, { session, clip }),
  deleteSession: (session: string) => post<{ ok: boolean; counts: Counts }>(`${base()}/delete_session`, { session }),
  recordingUrl: (session: string) => `${base()}/files/${session}/recording.wav`,
  clipUrl: (session: string, clip: string) => `${base()}/files/${session}/clips/${encodeURIComponent(clip)}`,
};
