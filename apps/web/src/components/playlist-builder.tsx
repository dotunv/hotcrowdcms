"use client";

import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { PlaylistItem, PlaylistPayload, PlaylistStatus, TransitionEffect } from "@/lib/types";
import { useToast } from "@/components/toast";

function formatLoop(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}m ${String(rest).padStart(2, "0")}s`;
}

function SortableItem({
  item,
  onDuration,
  onPreview,
  onRemove,
}: {
  item: PlaylistItem;
  onDuration: (duration: number) => void;
  onPreview: () => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: String(item.id) });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex items-center gap-3 rounded-xl border border-border-light bg-white p-3 shadow-sm dark:border-border-dark dark:bg-surface-dark ${isDragging ? "z-10 opacity-80 shadow-lg" : ""}`}
    >
      <button type="button" className="cursor-grab touch-none px-1 text-gray-400" aria-label="Drag to reorder" {...attributes} {...listeners}>
        ⋮⋮
      </button>
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
            onChange={(event) => onDuration(Number(event.target.value))}
            className="ml-2 w-16 rounded border px-1 py-0.5 text-sm"
          />
          s
        </label>
      </div>
      <button type="button" onClick={onPreview} className="text-sm text-primary">
        Play
      </button>
      <button type="button" onClick={onRemove} className="text-sm text-red-600">
        Remove
      </button>
    </div>
  );
}

export function PlaylistBuilder({ playlistId }: { playlistId: string }) {
  const toast = useToast();
  const client = useQueryClient();
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [previewIndex, setPreviewIndex] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

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
  const playlistRef = useRef(playlist);
  playlistRef.current = playlist;

  const replace = (next: PlaylistPayload) => {
    client.setQueryData(["playlist", playlistId], next);
  };

  const saveSettings = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patchPlaylist(playlistId, body),
    onSuccess: (data) => {
      replace(data);
      setDirty(false);
      setError("");
      toast("Playlist saved.");
    },
    onError: () => setError("Could not save playlist settings."),
  });

  const add = useMutation({
    mutationFn: (mediaId: string) => api.addItem(playlistId, mediaId),
    onSuccess: (data) => {
      replace(data);
      toast("Added to the loop.");
    },
    onError: () => setError("Could not add media."),
  });

  const remove = useMutation({
    mutationFn: (itemId: number) => api.removeItem(playlistId, itemId),
    onMutate: async (itemId) => {
      const previous = client.getQueryData<PlaylistPayload>(["playlist", playlistId]);
      if (previous) {
        replace({ ...previous, items: previous.items.filter((item) => item.id !== itemId) });
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

  function persistSettings() {
    const current = playlistRef.current;
    if (!current) return;
    saveSettings.mutate({
      name: current.name,
      status: current.status,
      is_loop: current.is_loop,
      assigned_screen_ids: current.assigned_screen_ids,
      transition_effect: current.transition_effect,
      schedule_type: current.schedule_type,
      start_date: current.start_date,
      end_date: current.end_date,
      start_time: current.start_time,
      end_time: current.end_time,
    });
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key === "s") {
        event.preventDefault();
        persistSettings();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [playlistId]);

  const reorder = useMutation({
    mutationFn: (itemIds: number[]) => api.reorder(playlistId, itemIds),
    onError: () => {
      void playlistQuery.refetch();
      setError("Could not reorder.");
    },
    onSuccess: replace,
  });

  function onDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!playlist || !over || active.id === over.id) return;
    const oldIndex = items.findIndex((item) => String(item.id) === String(active.id));
    const newIndex = items.findIndex((item) => String(item.id) === String(over.id));
    if (oldIndex < 0 || newIndex < 0) return;
    const next = arrayMove(items, oldIndex, newIndex).map((item, position) => ({ ...item, position }));
    replace({ ...playlist, items: next });
    reorder.mutate(next.map((item) => item.id));
  }

  const assigned = new Set(playlist?.assigned_screen_ids ?? []);
  const previewItem: PlaylistItem | undefined = previewIndex === null ? undefined : items[previewIndex];
  const publishLabel = useMemo(() => (playlist?.status === "ACTIVE" ? "Published" : "Publish"), [playlist]);

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
          <p className="hidden text-xs text-gray-500 md:block">
            Loop {formatLoop(playlist.total_duration)} · ⌘S to save
          </p>
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
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext items={items.map((item) => String(item.id))} strategy={verticalListSortingStrategy}>
              {items.map((item, index) => (
                <SortableItem
                  key={item.id}
                  item={item}
                  onDuration={(duration) => {
                    replace({
                      ...playlist,
                      items: items.map((row) => (row.id === item.id ? { ...row, duration } : row)),
                    });
                    durationMut.mutate({ itemId: item.id, duration });
                  }}
                  onPreview={() => setPreviewIndex(index)}
                  onRemove={() => remove.mutate(item.id)}
                />
              ))}
            </SortableContext>
          </DndContext>
          {items.length === 0 ? (
            <div className="flex h-full min-h-[240px] items-center justify-center rounded-2xl border border-dashed text-sm text-gray-500">
              Click media on the left to build the loop. Drag to reorder.
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
          <label className="block text-sm">
            Schedule
            <select
              value={playlist.schedule_type}
              onChange={(event) => {
                setDirty(true);
                replace({ ...playlist, schedule_type: event.target.value as PlaylistPayload["schedule_type"] });
              }}
              className="mt-1 w-full rounded-xl border px-2 py-2"
            >
              <option value="ALWAYS">Always on</option>
              <option value="SCHEDULED">Scheduled window</option>
            </select>
          </label>
          {playlist.schedule_type === "SCHEDULED" ? (
            <div className="grid grid-cols-2 gap-2 text-sm">
              <label>
                Start date
                <input
                  type="date"
                  className="mt-1 w-full rounded-lg border px-2 py-1"
                  value={playlist.start_date}
                  onChange={(event) => {
                    setDirty(true);
                    replace({ ...playlist, start_date: event.target.value });
                  }}
                />
              </label>
              <label>
                End date
                <input
                  type="date"
                  className="mt-1 w-full rounded-lg border px-2 py-1"
                  value={playlist.end_date}
                  onChange={(event) => {
                    setDirty(true);
                    replace({ ...playlist, end_date: event.target.value });
                  }}
                />
              </label>
              <label>
                Start time
                <input
                  type="time"
                  className="mt-1 w-full rounded-lg border px-2 py-1"
                  value={playlist.start_time}
                  onChange={(event) => {
                    setDirty(true);
                    replace({ ...playlist, start_time: event.target.value });
                  }}
                />
              </label>
              <label>
                End time
                <input
                  type="time"
                  className="mt-1 w-full rounded-lg border px-2 py-1"
                  value={playlist.end_time}
                  onChange={(event) => {
                    setDirty(true);
                    replace({ ...playlist, end_time: event.target.value });
                  }}
                />
              </label>
            </div>
          ) : null}
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
