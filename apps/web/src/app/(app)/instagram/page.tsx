"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast";
import { Page, Section, ui } from "@/components/ui";

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
    <Page
      eyebrow="Import"
      title="Instagram"
      narrow
      subtitle="Import a public media URL, or connect a Graph API token and sync recent posts on Pro. This uses Instagram's official API, not a password login."
    >
      <Section title="Import a file URL">
        <div className="flex flex-col gap-4 pt-5">
          <input className={ui.input} placeholder="https://..." value={url} onChange={(e) => setUrl(e.target.value)} />
          <div>
            <button type="button" className={ui.btnPrimary} onClick={() => importUrl.mutate()}>
              Add to library
            </button>
          </div>
          {importUrl.isError ? <p className={ui.error}>{(importUrl.error as Error).message}</p> : null}
        </div>
      </Section>
      <Section
        title="Graph API"
        link={
          <span className={`text-xs font-bold uppercase tracking-[0.1em] ${data?.connected ? "text-primary dark:text-[#B2F2BB]" : ui.muted}`}>
            {data?.connected ? "Connected" : "Not connected"}
          </span>
        }
      >
        <div className="flex flex-col gap-4 pt-5">
          <p className={`text-[15px] font-medium ${ui.muted}`}>{data?.connected ? "Connected." : "Paste a long-lived Instagram Graph token."}</p>
          {!data?.connected ? (
            <>
              <input className={ui.input} placeholder="Access token" value={token} onChange={(e) => setToken(e.target.value)} />
              <div>
                <button type="button" className={ui.btnGhost} onClick={() => connect.mutate()}>
                  Save token
                </button>
              </div>
            </>
          ) : (
            <div className="flex gap-3">
              <button type="button" className={ui.btnPrimary} onClick={() => sync.mutate()}>
                Sync recent posts
              </button>
              <button type="button" className={ui.btnGhost} onClick={() => disconnect.mutate()}>
                Disconnect
              </button>
            </div>
          )}
          {sync.isError ? <p className={ui.error}>{(sync.error as Error).message}</p> : null}
          {data && !data.sync_allowed ? <p className={`text-sm font-medium ${ui.muted}`}>Sync requires Pro. URL import works on Starter.</p> : null}
        </div>
      </Section>
    </Page>
  );
}
