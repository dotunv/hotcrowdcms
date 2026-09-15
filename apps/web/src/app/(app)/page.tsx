"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const dash = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const data = dash.data;
  const empty = data && (data.total_screens === 0 || data.total_media === 0);

  return (
    <div className="p-8 h-full overflow-y-auto space-y-8">
      <div className="flex justify-between items-end gap-4">
        <div>
          <h1 className="text-3xl font-bold">{data?.store_name ?? "Your store"}</h1>
          <p className="text-gray-500 mt-1">Pair a screen, add media, publish a playlist.</p>
        </div>
        <div className="flex gap-3">
          <Link href="/screens" className="px-4 py-2 bg-white dark:bg-surface-dark border rounded-xl text-sm font-bold">
            Connect screen
          </Link>
          <Link href="/playlists" className="px-4 py-2 bg-primary text-white rounded-xl text-sm font-bold">
            New playlist
          </Link>
        </div>
      </div>
      {empty ? (
        <div className="rounded-2xl border border-dashed border-primary/40 bg-primary/5 p-8">
          <h2 className="text-lg font-bold">Get a TV playing in a minute</h2>
          <p className="text-sm text-gray-500 mt-1">Open the player, enter the code, then drop files into a playlist.</p>
          <div className="flex gap-3 mt-6">
            <Link href="/screens" className="px-4 py-2 bg-primary text-white text-sm font-bold rounded-xl">
              1. Connect a screen
            </Link>
            <Link href="/library" className="px-4 py-2 bg-white dark:bg-surface-dark border text-sm font-bold rounded-xl">
              2. Add media
            </Link>
          </div>
        </div>
      ) : null}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          ["Screens online", `${data?.online_screens ?? 0}/${data?.total_screens ?? 0}`],
          ["Playlists", String(data?.total_playlists ?? 0)],
          ["Library", String(data?.total_media ?? 0)],
          ["Last publish", data?.last_publish ? data.last_publish.slice(0, 10) : "Never"],
        ].map(([label, value]) => (
          <div key={label} className="bg-white dark:bg-surface-dark rounded-2xl border p-6">
            <p className="text-sm text-gray-500">{label}</p>
            <p className="text-2xl font-bold mt-2">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
