"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { PlaylistItem, PlaylistPayload, PlaylistStatus, TransitionEffect } from "@/lib/types";

function formatLoop(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}m ${String(rest).padStart(2, "0")}s`;
}

export function PlaylistBuilder({ playlistId }: { playlistId: string }) {
  const client = useQueryClient();
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [previewIndex, setPreviewIndex] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);

  const playlistQuery = useQuery({
    queryKey: ["playlist", playlistId],
    queryFn: () => api.playlist(playlistId),
  });
  const mediaQuery = useQuery({
    queryKey: ["media", query],
    queryFn: () => api.media(query),
  });
  const screensQuery = useQuery({
    queryKey: ["screens"],
    queryFn: api.screens,
  });

  const playlist = playlistQuery.data;
  const items = playlist?.items ?? [];

  const replace = (next: PlaylistPayload) => {
    client.setQueryData(["playlist", playlistId], next);
  };

  const saveSettings = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patchPlaylist(playlistId, body),
    onSuccess: (data) => {
      replace(data);
      setDirty(false);
      setError("");
    },
    onError: () => setError("Could not save playlist settings."),
  });

  const add = useMutation({
    mutationFn: (mediaId: string) => api.addItem(playlistId, mediaId),
    onSuccess: replace,
    onError: () => setError("Could not add media."),
  });

  const remove = useMutation({
    mutationFn: (itemId: number) => api.removeItem(playlistId, itemId),
    onMutate: async (itemId) => {
      const previous = client.getQueryData<PlaylistPayload>(["playlist", playlistId]);
      if (previous) {
        replace({
          ...previous,
          items: previous.items.filter((item) => item.id !== itemId),
        });
      }
      return { previous };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.previous) replace(ctx.previous);
      setError("Could not remove item.");
    },
    onSuccess: replace,
  });

  const durationMut = useMutation({
    mutationFn: ({ itemId, duration }: { itemId: number; duration: number }) =>
      api.patchItem(playlistId, itemId, duration),
    onSuccess: replace,
  });

  const reorder = useMutation({
    mutationFn: (itemIds: number[]) => api.reorder(playlistId, itemIds),
    onError: () => {
      void playlistQuery.refetch();
      setError("Could not reorder.");
    },
    onSuccess: replace,
  });

  const move = (index: number, direction: -1 | 1) => {
    const next = [...items];
    const target = index + direction;
    if (target < 0 || target >= next.length) return;
    const [row] = next.splice(index, 1);
    next.splice(target, 0, row);
    const optimistic: PlaylistPayload = {
      ...playlist!,
      items: next.map((item, position) => ({ ...item, position })),
    };
    replace(optimistic);
    reorder.mutate(next.map((item) => item.id));
  };

  const assigned = new Set(playlist?.assigned_screen_ids ?? []);
  const previewItem: PlaylistItem | undefined = previewIndex === null ? undefined : items[previewIndex];

  const publishLabel = useMemo(() => {
    if (!playlist) return "Publish";
    return playlist.status === "ACTIVE" ? "Published" : "Publish";
  }, [playlist]);

  if (playlistQuery.isLoading) {
    return <div className="h-full bg-background-light dark:bg-background-dark" />;
  }
  if (!playlist) {
    return <p className="p-8 text-sm text-gray-500">Playlist not found.</p>;
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-16 flex-shrink-0 items-center justify-between border-b border-border-light bg-white px-4 dark:border-border-dark dark:bg-surface-dark">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/playlists" className="text-sm text-gray-500 hover:text-primary">
            Playlists
          </Link>
          <span className="text-gray-400">/</span>
          <input
            value={playlist.name}
            onChange={(event) => {
              setDirty(true);
              replace({ ...playlist, name: event.target.value });
            }}
            className="max-w-[240px] bg-transparent font-semibold text-gray-900 outline-none dark:text-white"
          />
          <span
            className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase ${
              playlist.status === "ACTIVE" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-800"
            }`}
          >
            {playlist.status.toLowerCase()}
          </span>
          {dirty ? <span className="h-2.5 w-2.5 rounded-full bg-amber-500" title="Unsaved changes" /> : null}
        </div>
        <div className="flex items-center gap-2">
          <p className="hidden text-xs text-gray-500 md:block">Loop {formatLoop(playlist.total_duration)}</p>
          <button type="button" onClick={() => setPreviewIndex(0)} disabled={items.length === 0} className="px-3 py-1.5 text-sm">
            Preview
          </button>
          <button
            type="button"
            onClick={() => saveSettings.mutate({ name: playlist.name, status: "DRAFT" satisfies PlaylistStatus })}
            className="rounded-lg px-3 py-1.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            Save draft
          </button>
          <button
            type="button"
            onClick={() =>
              saveSettings.mutate({
                name: playlist.name,
                status: "ACTIVE" satisfies PlaylistStatus,
                is_loop: playlist.is_loop,
                assigned_screen_ids: playlist.assigned_screen_ids,
                transition_effect: playlist.transition_effect,
                schedule_type: playlist.schedule_type,
                start_date: playlist.start_date,
                end_date: playlist.end_date,
                start_time: playlist.start_time,
                end_time: playlist.end_time,
              })
            }
            className="rounded-lg bg-primary px-4 py-1.5 text-sm font-bold text-white"
          >
            {publishLabel}
          </button>
        </div>
      </header>

      {error ? <div className="bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div> : null}

      <div className="flex min-h-0 flex-1">
        <aside className="flex w-72 flex-col border-r border-border-light bg-white dark:border-border-dark dark:bg-surface-dark">
          <div className="p-3">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search library"
              className="w-full rounded-xl border border-border-light bg-gray-50 px-3 py-2 text-sm dark:border-border-dark dark:bg-gray-800"
            />
          </div>
          <div className="flex-1 space-y-2 overflow-y-auto p-3">
            {(mediaQuery.data?.results ?? []).map((media) => (
              <button
                key={media.id}
                type="button"
                onClick={() => add.mutate(media.id)}
                className="flex w-full items-center gap-2 rounded-xl border border-border-light p-2 text-left hover:border-primary/50"
              >
                {media.type === "image" && media.url ? (
                  <img src={media.url} alt="" className="h-12 w-12 rounded-lg object-cover" />
                ) : (
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-gray-100 text-xs">VID</div>
                )}
                <span className="truncate text-sm font-medium">{media.name}</span>
              </button>
            ))}
            {(mediaQuery.data?.results ?? []).length === 0 ? (
              <p className="p-2 text-sm text-gray-500">Add files in Library, then click to insert them here.</p>
            ) : null}
          </div>
        </aside>

        <section className="flex-1 space-y-2 overflow-y-auto p-4">
          {items.map((item, index) => (
            <div key={item.id} className="flex items-center gap-3 rounded-xl border border-border-light bg-white p-3 dark:bg-surface-dark">
              <div className="flex flex-col">
                <button type="button" onClick={() => move(index, -1)} className="text-gray-400 hover:text-gray-700" aria-label="Move up">
                  ↑
                </button>
                <button type="button" onClick={() => move(index, 1)} className="text-gray-400 hover:text-gray-700" aria-label="Move down">
                  ↓
                </button>
              </div>
              {item.type === "image" && item.url ? (
                <img src={item.url} alt="" className="h-16 w-16 rounded-lg object-cover" />
              ) : (
                <div className="h-16 w-16 rounded-lg bg-gray-100" />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">{item.name}</p>
                <label className="text-xs text-gray-500">
                  Duration
                  <input
                    type="number"
                    min={1}
                    value={item.duration}
                    onChange={(event) => {
                      const duration = Number(event.target.value);
                      replace({
                        ...playlist,
                        items: items.map((row) => (row.id === item.id ? { ...row, duration } : row)),
                      });
                      durationMut.mutate({ itemId: item.id, duration });
                    }}
                    className="ml-2 w-16 rounded border px-1 py-0.5 text-sm"
                  />
                  s
                </label>
              </div>
              <button type="button" onClick={() => setPreviewIndex(index)} className="text-sm text-primary">
                Play
              </button>
              <button type="button" onClick={() => remove.mutate(item.id)} className="text-sm text-red-600">
                Remove
              </button>
            </div>
          ))}
          {items.length === 0 ? (
            <div className="flex h-full min-h-[240px] items-center justify-center rounded-2xl border border-dashed text-sm text-gray-500">
              Click media on the left to build the loop.
            </div>
          ) : null}
        </section>

        <aside className="w-80 space-y-4 overflow-y-auto border-l border-border-light bg-white p-4 dark:border-border-dark dark:bg-surface-dark">
          <h2 className="font-bold">Playback</h2>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={playlist.is_loop}
              onChange={(event) => {
                setDirty(true);
                replace({ ...playlist, is_loop: event.target.checked });
              }}
            />
            Loop
          </label>
          <label className="block text-sm">
            Transition
            <select
              value={playlist.transition_effect}
              onChange={(event) => {
                setDirty(true);
                replace({ ...playlist, transition_effect: event.target.value as TransitionEffect });
              }}
              className="mt-1 w-full rounded-xl border px-2 py-2"
            >
              <option value="FADE">Fade</option>
              <option value="SLIDE">Slide</option>
              <option value="NONE">None</option>
            </select>
          </label>
          <h2 className="pt-2 font-bold">Screens</h2>
          <div className="space-y-2">
            {(screensQuery.data?.results ?? []).map((screen) => (
              <label key={screen.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={assigned.has(screen.id)}
                  onChange={(event) => {
                    const next = new Set(assigned);
                    if (event.target.checked) next.add(screen.id);
                    else next.delete(screen.id);
                    setDirty(true);
                    replace({ ...playlist, assigned_screen_ids: [...next] });
                  }}
                />
                <span>{screen.name}</span>
                <span className={screen.online ? "text-green-600" : "text-gray-400"}>{screen.online ? "online" : "offline"}</span>
              </label>
            ))}
            {(screensQuery.data?.results ?? []).length === 0 ? (
              <p className="text-sm text-gray-500">Connect a screen first.</p>
            ) : null}
          </div>
        </aside>
      </div>

      {previewItem ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6" onClick={() => setPreviewIndex(null)}>
          <div className="w-full max-w-3xl" onClick={(event) => event.stopPropagation()}>
            {previewItem.type === "video" && previewItem.url ? (
              <video src={previewItem.url} controls autoPlay className="w-full rounded-xl" />
            ) : previewItem.url ? (
              <img src={previewItem.url} alt={previewItem.name} className="w-full rounded-xl" />
            ) : null}
            <div className="mt-3 flex justify-between text-sm text-white">
              <button type="button" onClick={() => setPreviewIndex(Math.max(0, (previewIndex ?? 0) - 1))}>
                Previous
              </button>
              <span>
                {previewItem.name} · {previewItem.duration}s — same payload the player requests
              </span>
              <button type="button" onClick={() => setPreviewIndex(Math.min(items.length - 1, (previewIndex ?? 0) + 1))}>
                Next
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
