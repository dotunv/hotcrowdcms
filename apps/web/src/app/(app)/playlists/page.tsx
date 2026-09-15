"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { DeleteDialog } from "@/components/delete-dialog";
import { api } from "@/lib/api";

export default function PlaylistsPage() {
  const router = useRouter();
  const client = useQueryClient();
  const list = useQuery({ queryKey: ["playlists"], queryFn: api.playlists });
  const [pending, setPending] = useState<{ id: string; name: string } | null>(null);
  const create = useMutation({
    mutationFn: () => api.createPlaylist("Untitled playlist"),
    onSuccess: (playlist) => router.push(`/playlists/${playlist.id}`),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deletePlaylist(id),
    onSuccess: () => {
      setPending(null);
      void client.invalidateQueries({ queryKey: ["playlists"] });
    },
  });

  return (
    <div className="p-8 h-full overflow-y-auto">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-3xl font-bold">Playlists</h1>
          <p className="text-gray-500 mt-1">Build a loop, publish it, assign it to screens.</p>
        </div>
        <button type="button" onClick={() => create.mutate()} className="px-4 py-2 bg-primary text-white text-sm font-bold rounded-xl">
          New playlist
        </button>
      </div>
      <div className="grid gap-4">
        {(list.data?.results ?? []).map((playlist) => (
          <div key={playlist.id} className="bg-white dark:bg-surface-dark rounded-2xl border p-5 flex justify-between items-center">
            <div>
              <Link href={`/playlists/${playlist.id}`} className="text-lg font-bold hover:text-primary">
                {playlist.name}
              </Link>
              <p className="text-sm text-gray-500 mt-1">
                {playlist.item_count} items · {playlist.status.toLowerCase()}
              </p>
            </div>
            <div className="flex gap-2">
              <Link href={`/playlists/${playlist.id}`} className="px-3 py-2 text-sm font-bold border rounded-xl">
                Edit
              </Link>
              <button type="button" className="px-3 py-2 text-sm text-red-600" onClick={() => setPending(playlist)}>
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
      <DeleteDialog
        open={Boolean(pending)}
        title="Delete this playlist"
        name={pending?.name ?? ""}
        hint="Screens using it will have no playlist until you assign another."
        pending={remove.isPending}
        onClose={() => setPending(null)}
        onConfirm={() => pending && remove.mutate(pending.id)}
      />
    </div>
  );
}
