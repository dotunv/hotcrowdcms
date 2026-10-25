"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { DeleteDialog } from "@/components/delete-dialog";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast";
import { EmptyNote, Page, StatStrip, ui } from "@/components/ui";

export default function ScreensPage() {
  const toast = useToast();
  const client = useQueryClient();
  const screens = useQuery({ queryKey: ["screens"], queryFn: api.screens, refetchInterval: 10000 });
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [error, setError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<{ id: string; name: string } | null>(null);

  const pair = useMutation({
    mutationFn: async () => {
      const check = await api.validateCode(code);
      if (!check.valid) throw new Error(check.message || "Invalid code");
      return api.pairScreen({ pairing_code: code, name, location });
    },
    onSuccess: () => {
      setOpen(false);
      setCode("");
      setName("");
      setLocation("");
      void client.invalidateQueries({ queryKey: ["screens"] });
      void client.invalidateQueries({ queryKey: ["dashboard"] });
      toast("Screen connected.");
    },
    onError: (err: Error) => setError(err.message),
  });

  const assign = useMutation({
    mutationFn: ({ id, playlist_id }: { id: string; playlist_id: string | null }) => api.assignScreen(id, playlist_id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["screens"] });
      void client.invalidateQueries({ queryKey: ["dashboard"] });
      toast("Playlist assigned.");
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteScreen(id),
    onSuccess: () => {
      setPendingDelete(null);
      void client.invalidateQueries({ queryKey: ["screens"] });
      void client.invalidateQueries({ queryKey: ["dashboard"] });
      toast("Screen removed.");
    },
  });

  const data = screens.data;

  return (
    <Page
      eyebrow="Devices"
      title="Screens"
      subtitle="Status updates every 10 seconds from device heartbeats."
      actions={
        <button type="button" onClick={() => setOpen(true)} className={ui.btnPrimary}>
          Connect screen
        </button>
      }
    >
      <StatStrip
        items={[
          ["devices", data?.total ?? 0],
          ["online", data?.online ?? 0],
          ["offline", data?.offline ?? 0],
        ]}
      />
      <section>
        <div className={`flex items-center gap-4 pb-3.5 ${ui.sectionHead}`}>
          <span className="w-24 shrink-0 text-xs font-semibold uppercase tracking-[0.14em]">Status</span>
          <span className="flex-1 text-xs font-semibold uppercase tracking-[0.14em]">Screen</span>
          <span className="w-56 shrink-0 text-xs font-semibold uppercase tracking-[0.14em]">Playlist</span>
          <span className="w-8 shrink-0" />
        </div>
        {(data?.results ?? []).map((screen) => (
          <div key={screen.id} className={`flex items-center gap-4 py-4 ${ui.row}`}>
            <span className="flex w-24 shrink-0 items-center gap-2.5 text-[13px] font-bold">
              <span className={`h-2.5 w-2.5 rounded-full ${screen.online ? "bg-primary dark:bg-[#B2F2BB]" : "bg-[#C4C8C0] dark:bg-[#6B746C]"}`} />
              <span className={screen.online ? "text-primary dark:text-[#B2F2BB]" : "text-[#C2410C] dark:text-[#FB923C]"}>
                {screen.online ? "Online" : "Offline"}
              </span>
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[15px] font-bold">{screen.name}</p>
              <p className={`truncate text-[13px] font-medium ${ui.muted}`}>{screen.location || "No location"}</p>
            </div>
            <select
              className={`${ui.input} w-56 shrink-0 py-2 dark:[&>option]:bg-[#111513]`}
              value={screen.playlist_id ?? ""}
              onChange={(event) => assign.mutate({ id: screen.id, playlist_id: event.target.value || null })}
            >
              <option value="">No playlist</option>
              {(data?.playlists ?? []).map((playlist) => (
                <option key={playlist.id} value={playlist.id}>
                  {playlist.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              className={`flex w-8 shrink-0 justify-end ${ui.muted} hover:text-[#C2410C]`}
              title="Remove screen"
              onClick={() => setPendingDelete(screen)}
            >
              <span className="material-symbols-outlined text-xl">delete</span>
            </button>
          </div>
        ))}
        {(data?.results ?? []).length === 0 ? (
          <div className="pt-6">
            <EmptyNote>No screens yet. Open the player and enter the pairing code.</EmptyNote>
          </div>
        ) : null}
      </section>

      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          <div className={ui.overlay} onClick={() => setOpen(false)} />
          <form
            className={`${ui.modal} max-w-md space-y-5`}
            onSubmit={(event) => {
              event.preventDefault();
              setError("");
              pair.mutate();
            }}
          >
            <div>
              <p className={ui.eyebrow}>Step 1</p>
              <h3 className="mt-2 text-[28px] font-extrabold leading-8 tracking-[-0.03em]">Connect a screen</h3>
              <p className={`mt-2 text-sm font-medium ${ui.muted}`}>Enter the code shown on your TV after you open the player.</p>
            </div>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))}
              maxLength={8}
              placeholder="ABCD2345"
              className="w-full rounded-2xl bg-[#0E1A14] py-5 text-center font-mono text-4xl font-extrabold uppercase tracking-[0.3em] text-white placeholder:text-[#3A443C] focus:outline-none dark:bg-[#111513]"
            />
            {error ? <p className={ui.error}>{error}</p> : null}
            <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Front window" className={ui.input} />
            <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Location (optional)" className={ui.input} />
            <div className="flex gap-3">
              <button type="button" onClick={() => setOpen(false)} className={`${ui.btnGhost} flex-1`}>
                Cancel
              </button>
              <button type="submit" disabled={pair.isPending || code.length < 8 || !name.trim()} className={`${ui.btnPrimary} flex-1`}>
                {pair.isPending ? "Connecting…" : "Connect"}
              </button>
            </div>
          </form>
        </div>
      ) : null}

      <DeleteDialog
        open={Boolean(pendingDelete)}
        title="Remove this screen"
        name={pendingDelete?.name ?? ""}
        hint="The display will need a new pairing code to reconnect."
        pending={remove.isPending}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => pendingDelete && remove.mutate(pendingDelete.id)}
      />
    </Page>
  );
}
