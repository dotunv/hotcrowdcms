"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast";

export default function InstagramPage() {
  const toast = useToast();
  const client = useQueryClient();
  const status = useQuery({ queryKey: ["instagram"], queryFn: api.instagramStatus });
  const [token, setToken] = useState("");
  const [url, setUrl] = useState("");
  const connect = useMutation({
    mutationFn: () => api.instagramConnect(token),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["instagram"] });
      toast("Instagram connected.");
    },
  });
  const disconnect = useMutation({
    mutationFn: api.instagramDisconnect,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["instagram"] });
      toast("Disconnected.");
    },
  });
  const importUrl = useMutation({
    mutationFn: () => api.instagramImport(url),
    onSuccess: () => {
      setUrl("");
      void client.invalidateQueries({ queryKey: ["media"] });
      toast("Imported into the library.");
    },
  });
  const sync = useMutation({
    mutationFn: api.instagramSync,
    onSuccess: (data) => {
      void client.invalidateQueries({ queryKey: ["media"] });
      toast(`Imported ${data.imported} posts.`);
    },
  });

  const data = status.data;
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold">Instagram</h1>
        <p className="mt-1 text-sm text-gray-500">
          Import a public media URL, or connect a Graph API token and sync recent posts on Pro. This uses Instagram&apos;s official API, not a password login.
        </p>
      </div>
      <section className="space-y-3 rounded-2xl border bg-white p-6 dark:bg-surface-dark">
        <h2 className="font-bold">Import a file URL</h2>
        <input className="w-full rounded-xl border px-3 py-2" placeholder="https://..." value={url} onChange={(e) => setUrl(e.target.value)} />
        <button type="button" className="rounded-xl bg-primary px-4 py-2 text-sm font-bold text-white" onClick={() => importUrl.mutate()}>
          Add to library
        </button>
        {importUrl.isError ? <p className="text-sm text-red-600">{(importUrl.error as Error).message}</p> : null}
      </section>
      <section className="space-y-3 rounded-2xl border bg-white p-6 dark:bg-surface-dark">
        <h2 className="font-bold">Graph API</h2>
        <p className="text-sm text-gray-500">{data?.connected ? "Connected." : "Paste a long-lived Instagram Graph token."}</p>
        {!data?.connected ? (
          <>
            <input className="w-full rounded-xl border px-3 py-2" placeholder="Access token" value={token} onChange={(e) => setToken(e.target.value)} />
            <button type="button" className="rounded-xl border px-4 py-2 text-sm font-bold" onClick={() => connect.mutate()}>
              Save token
            </button>
          </>
        ) : (
          <div className="flex gap-2">
            <button type="button" className="rounded-xl bg-primary px-4 py-2 text-sm font-bold text-white" onClick={() => sync.mutate()}>
              Sync recent posts
            </button>
            <button type="button" className="rounded-xl border px-4 py-2 text-sm" onClick={() => disconnect.mutate()}>
              Disconnect
            </button>
          </div>
        )}
        {sync.isError ? <p className="text-sm text-red-600">{(sync.error as Error).message}</p> : null}
        {data && !data.sync_allowed ? <p className="text-sm text-gray-500">Sync requires Pro. URL import works on Starter.</p> : null}
      </section>
    </div>
  );
}
