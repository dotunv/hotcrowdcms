import type { Dashboard, Me, MediaItem, PlaylistPayload, ScreenRow } from "./types";

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(url, { ...init, headers, credentials: "include" });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
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
  uploadMedia: (form: FormData) => request<MediaItem>("/api/v1/media", { method: "POST", body: form }),
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
