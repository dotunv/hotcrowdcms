"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const dash = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const data = dash.data;
  const empty = data && (data.total_screens === 0 || data.total_media === 0);

  return (
    <div className="space-y-8 overflow-y-auto p-8 h-full">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">{data?.store_name ?? "Your store"}</h1>
          <p className="mt-1 text-gray-500">
            Pair a screen, add media, publish a playlist
            {data?.last_heartbeat ? ` · last heartbeat ${data.last_heartbeat.slice(11, 16)} UTC` : ""}.
          </p>
        </div>
        <div className="flex gap-3">
          <Link href="/screens" className="rounded-xl border bg-white px-4 py-2 text-sm font-bold dark:bg-surface-dark">
            Connect screen
          </Link>
          <Link href="/playlists" className="rounded-xl bg-primary px-4 py-2 text-sm font-bold text-white">
            New playlist
          </Link>
        </div>
      </div>
      {empty ? (
        <div className="rounded-2xl border border-dashed border-primary/40 bg-primary/5 p-8">
          <h2 className="text-lg font-bold">Get a TV playing in a minute</h2>
          <p className="mt-1 text-sm text-gray-500">Open the player, enter the code, then drop files into a playlist.</p>
          <div className="mt-6 flex gap-3">
            <Link href="/screens" className="rounded-xl bg-primary px-4 py-2 text-sm font-bold text-white">
              1. Connect a screen
            </Link>
            <Link href="/library" className="rounded-xl border bg-white px-4 py-2 text-sm font-bold dark:bg-surface-dark">
              2. Add media
            </Link>
          </div>
        </div>
      ) : null}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          ["Screens online", `${data?.online_screens ?? 0}/${data?.total_screens ?? 0}`],
          ["Playlists", String(data?.total_playlists ?? 0)],
          ["Library", String(data?.total_media ?? 0)],
          ["Last publish", data?.last_publish ? data.last_publish.slice(0, 10) : "Never"],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl border bg-white p-6 dark:bg-surface-dark">
            <p className="text-sm text-gray-500">{label}</p>
            <p className="mt-2 text-2xl font-bold">{value}</p>
          </div>
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border bg-white p-6 dark:bg-surface-dark">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-bold">Screens</h2>
            <Link href="/screens" className="text-sm font-semibold text-primary">
              View all
            </Link>
          </div>
          <ul className="space-y-3">
            {(data?.screens ?? []).map((screen) => (
              <li key={screen.id} className="flex items-center justify-between gap-3 text-sm">
                <div>
                  <p className="font-semibold">{screen.name}</p>
                  <p className="text-gray-500">{screen.playlist_name || "No playlist"}</p>
                </div>
                <span className={screen.online ? "font-semibold text-green-600" : "text-gray-400"}>
                  {screen.online ? "Online" : "Offline"}
                </span>
              </li>
            ))}
            {(data?.screens ?? []).length === 0 ? <p className="text-sm text-gray-500">No screens yet.</p> : null}
          </ul>
        </section>
        <section className="rounded-2xl border bg-white p-6 dark:bg-surface-dark">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-bold">Recent media</h2>
            <Link href="/library" className="text-sm font-semibold text-primary">
              Library
            </Link>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {(data?.recent_media ?? []).map((item) => (
              <Link key={item.id} href="/library" className="overflow-hidden rounded-xl bg-gray-100 dark:bg-gray-800">
                <div className="aspect-square">
                  {item.type === "image" && item.url ? (
                    <img src={item.url} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs text-gray-400">VID</div>
                  )}
                </div>
                <p className="truncate px-2 py-2 text-xs font-medium">{item.name}</p>
              </Link>
            ))}
          </div>
          {(data?.recent_media ?? []).length === 0 ? <p className="text-sm text-gray-500">Nothing uploaded yet.</p> : null}
        </section>
      </div>
    </div>
  );
}
