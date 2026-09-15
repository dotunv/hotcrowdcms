import type { Dashboard, Me, MediaItem, PlaylistPayload, ScreenRow } from "./types";

const AUTH_SKIP_REFRESH = ["/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh", "/api/v1/auth/logout"];

let refreshInFlight: Promise<boolean> | null = null;

function readError(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body && typeof (body as { detail: unknown }).detail === "string") {
    return (body as { detail: string }).detail;
  }
  return `Request failed (${status})`;
}

async function tryRefresh(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch("/api/v1/auth/refresh", { method: "POST", credentials: "include" })
      .then((response) => response.ok)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

async function request<T>(url: string, init: RequestInit = {}, retried = false): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(url, { ...init, headers, credentials: "include" });
  if (response.status === 401 && !retried && !AUTH_SKIP_REFRESH.some((path) => url.startsWith(path))) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(url, init, true);
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      detail = readError(await response.json(), response.status);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function uploadWithProgress(form: FormData, onProgress?: (percent: number) => void): Promise<MediaItem> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v1/media");
    xhr.withCredentials = true;
    xhr.upload.onprogress = (event) => {
      if (!onProgress || !event.lengthComputable) return;
      onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as MediaItem);
        return;
      }
      try {
        reject(new Error(readError(JSON.parse(xhr.responseText), xhr.status)));
      } catch {
        reject(new Error(`Request failed (${xhr.status})`));
      }
    };
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(form);
  });
}

export const api = {
  me: () => request<Me>("/api/v1/auth/me"),
  login: (login: string, password: string) =>
    request<Me>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ login, password }) }),
  register: (username: string, email: string, password: string) =>
    request<Me>("/api/v1/auth/register", { method: "POST", body: JSON.stringify({ username, email, password }) }),
  logout: () => request<{ ok: boolean }>("/api/v1/auth/logout", { method: "POST" }),
  dashboard: () => request<Dashboard>("/api/v1/dashboard"),
  store: () => request<Me["store"]>("/api/v1/store"),
  patchStore: (body: Record<string, unknown>) =>
    request<Me["store"]>("/api/v1/store", { method: "PATCH", body: JSON.stringify(body) }),
  screens: () =>
    request<{
      total: number;
      online: number;
      offline: number;
      results: ScreenRow[];
      playlists: { id: string; name: string }[];
    }>("/api/v1/screens"),
  validateCode: (code: string) =>
    request<{ valid: boolean; message?: string }>(`/api/v1/screens/validate-code?code=${encodeURIComponent(code)}`),
  pairScreen: (body: { pairing_code: string; name: string; location: string }) =>
    request<ScreenRow>("/api/v1/screens/pair", { method: "POST", body: JSON.stringify(body) }),
  assignScreen: (id: string, playlist_id: string | null) =>
    request<ScreenRow>(`/api/v1/screens/${id}`, { method: "PATCH", body: JSON.stringify({ playlist_id }) }),
  deleteScreen: (id: string) => request<{ ok: boolean }>(`/api/v1/screens/${id}`, { method: "DELETE" }),
  media: (query = "", type = "") => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (type) params.set("type", type);
    return request<{ results: MediaItem[] }>(`/api/v1/media?${params.toString()}`);
  },
  uploadMedia: (form: FormData, onProgress?: (percent: number) => void) => uploadWithProgress(form, onProgress),
  deleteMedia: (id: string) => request<{ ok: boolean }>(`/api/v1/media/${id}`, { method: "DELETE" }),
  playlists: () =>
    request<{ results: { id: string; name: string; status: string; item_count: number; total_duration: number }[] }>(
      "/api/v1/playlists",
    ),
  createPlaylist: (name = "Untitled playlist") =>
    request<PlaylistPayload>("/api/v1/playlists", { method: "POST", body: JSON.stringify({ name }) }),
  playlist: (id: string) => request<PlaylistPayload>(`/api/v1/playlists/${id}`),
  patchPlaylist: (id: string, body: Record<string, unknown>) =>
    request<PlaylistPayload>(`/api/v1/playlists/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deletePlaylist: (id: string) => request<{ ok: boolean }>(`/api/v1/playlists/${id}`, { method: "DELETE" }),
  addItem: (id: string, mediaId: string) =>
    request<PlaylistPayload>(`/api/v1/playlists/${id}/items`, {
      method: "POST",
      body: JSON.stringify({ media_id: mediaId }),
    }),
  removeItem: (id: string, itemId: number) =>
    request<PlaylistPayload>(`/api/v1/playlists/${id}/items/${itemId}`, { method: "DELETE" }),
  patchItem: (id: string, itemId: number, duration: number) =>
    request<PlaylistPayload>(`/api/v1/playlists/${id}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ duration }),
    }),
  reorder: (id: string, itemIds: number[]) =>
    request<PlaylistPayload>(`/api/v1/playlists/${id}/reorder`, {
      method: "POST",
      body: JSON.stringify({ item_ids: itemIds }),
    }),
};
