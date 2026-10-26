"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { DeleteDialog } from "@/components/delete-dialog";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast";
import { EmptyNote, Page, StatusBadge, ui } from "@/components/ui";

export default function PlaylistsPage() {
  const toast = useToast();
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
      toast("Playlist deleted.");
    },
  });

  return (
    <Page
      eyebrow="Content"
      title="Playlists"
      subtitle="Build a loop, publish it, assign it to screens."
      actions={
        <button type="button" onClick={() => create.mutate()} className={ui.btnPrimary}>
          New playlist
        </button>
      }
    >
      <section>
        <div className={ui.sectionHead}>
          <h2 className={ui.sectionTitle}>All playlists</h2>
        </div>
        {(list.data?.results ?? []).map((playlist) => (
          <div key={playlist.id} className={`flex items-center gap-5 py-4 ${ui.row}`}>
            <Link href={`/playlists/${playlist.id}`} className="min-w-0 flex-1 truncate text-[17px] font-extrabold tracking-[-0.02em] hover:text-primary dark:hover:text-[#B2F2BB]">
              {playlist.name}
            </Link>
            <span className={`w-24 shrink-0 text-[13px] font-semibold ${ui.muted}`}>
              {playlist.item_count} {playlist.item_count === 1 ? "item" : "items"}
            </span>
            <span className="flex w-24 shrink-0 justify-end">
              <StatusBadge status={playlist.status} />
            </span>
            <div className="flex w-32 shrink-0 items-center justify-end gap-4">
              <Link href={`/playlists/${playlist.id}`} className={ui.btnSmall}>
                Edit
              </Link>
              <button type="button" className={ui.btnDanger} onClick={() => setPending(playlist)}>
                Delete
              </button>
            </div>
          </div>
        ))}
        {(list.data?.results ?? []).length === 0 ? (
          <div className="pt-6">
            <EmptyNote>No playlists yet. Create one and drop library files into the loop.</EmptyNote>
          </div>
        ) : null}
      </section>
      <DeleteDialog
        open={Boolean(pending)}
        title="Delete this playlist"
        name={pending?.name ?? ""}
        hint="Screens using it will have no playlist until you assign another."
        pending={remove.isPending}
        onClose={() => setPending(null)}
        onConfirm={() => pending && remove.mutate(pending.id)}
      />
    </Page>
  );
}
