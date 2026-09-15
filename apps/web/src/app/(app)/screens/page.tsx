"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { DeleteDialog } from "@/components/delete-dialog";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast";

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
    <div className="p-8 h-full overflow-y-auto space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold">Screens</h1>
          <p className="text-gray-500 mt-1">Status updates every 10 seconds from device heartbeats.</p>
        </div>
        <button type="button" onClick={() => setOpen(true)} className="px-4 py-2 bg-primary text-white text-sm font-bold rounded-xl">
          Connect screen
        </button>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Devices" value={data?.total ?? 0} />
        <Stat label="Online" value={data?.online ?? 0} />
        <Stat label="Offline" value={data?.offline ?? 0} />
      </div>
      <div className="bg-white dark:bg-surface-dark rounded-2xl border overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="text-xs font-bold text-gray-500 uppercase bg-gray-50 dark:bg-gray-800/50">
              <th className="px-6 py-4">Status</th>
              <th className="px-6 py-4">Screen</th>
              <th className="px-6 py-4">Location</th>
              <th className="px-6 py-4">Playlist</th>
              <th className="px-6 py-4" />
            </tr>
          </thead>
          <tbody>
            {(data?.results ?? []).map((screen) => (
              <tr key={screen.id} className="border-t border-border-light dark:border-border-dark">
                <td className="px-6 py-4 text-sm">
                  <span className="inline-flex items-center gap-2">
                    <span className={`h-2 w-2 rounded-full ${screen.online ? "bg-green-500" : "bg-gray-300"}`} />
                    {screen.online ? "Online" : "Offline"}
                  </span>
                </td>
                <td className="px-6 py-4 font-bold text-sm">{screen.name}</td>
                <td className="px-6 py-4 text-sm">{screen.location || "—"}</td>
                <td className="px-6 py-4">
                  <select
                    className="text-sm rounded-lg border px-2 py-1 bg-gray-50 dark:bg-gray-800"
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
                </td>
                <td className="px-6 py-4 text-right">
                  <button type="button" className="text-gray-400 hover:text-red-600" onClick={() => setPendingDelete(screen)}>
                    <span className="material-symbols-outlined">delete</span>
                  </button>
                </td>
              </tr>
            ))}
            {(data?.results ?? []).length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                  No screens yet. Open the player and enter the pairing code.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          <div className="absolute inset-0 bg-gray-900/50" onClick={() => setOpen(false)} />
          <form
            className="relative bg-white dark:bg-surface-dark w-full max-w-md rounded-2xl p-6 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              setError("");
              pair.mutate();
            }}
          >
            <h3 className="text-xl font-bold">Connect a screen</h3>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))}
              maxLength={8}
              placeholder="ABCD2345"
              className="w-full text-center text-3xl font-mono tracking-[0.3em] py-3 border rounded-xl uppercase"
            />
            {error ? <p className="text-red-500 text-sm">{error}</p> : null}
            <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Front window" className="w-full px-4 py-2.5 rounded-xl border" />
            <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Location (optional)" className="w-full px-4 py-2.5 rounded-xl border" />
            <div className="flex gap-3">
              <button type="button" onClick={() => setOpen(false)} className="flex-1 border rounded-xl font-bold py-2">
                Cancel
              </button>
              <button type="submit" disabled={pair.isPending || code.length < 8 || !name.trim()} className="flex-1 bg-primary text-white rounded-xl font-bold py-2 disabled:opacity-50">
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
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white dark:bg-surface-dark rounded-2xl p-6 border">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
    </div>
  );
}
