"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { DeleteDialog } from "@/components/delete-dialog";
import { api } from "@/lib/api";
import type { MediaItem } from "@/lib/types";
import { useToast } from "@/components/toast";
import { EmptyNote, Page, ui } from "@/components/ui";

export default function LibraryPage() {
  const toast = useToast();
  const client = useQueryClient();
  const [type, setType] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [pending, setPending] = useState<MediaItem | null>(null);
  const media = useQuery({ queryKey: ["media", type], queryFn: () => api.media("", type) });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteMedia(id),
    onSuccess: () => {
      setPending(null);
      void client.invalidateQueries({ queryKey: ["media"] });
      void client.invalidateQueries({ queryKey: ["dashboard"] });
      toast("File removed.");
    },
    onError: (err: Error) => {
      setPending(null);
      toast(err.message || "Could not remove the file.");
    },
  });

  const items = media.data?.results ?? [];
  const fallbacks = [
    "bg-[#B2F2BB]",
    "bg-[#0E1A14] dark:bg-[#1F2622]",
    "bg-[#FFD84D]",
    "bg-[#F3F4F1] dark:bg-[#2A322C]",
    "bg-[#045E33] dark:bg-[#057A43]",
  ];

  return (
    <Page
      eyebrow="Content"
      title="Library"
      subtitle="Images and videos that can play on a screen."
      actions={
        <button type="button" onClick={() => setUploadOpen(true)} className={ui.btnPrimary}>
          Upload
        </button>
      }
    >
      <div className="flex gap-2">
        {[
          ["", "All"],
          ["IMAGE", "Images"],
          ["VIDEO", "Videos"],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setType(value)}
            className={`rounded-lg px-3.5 py-1.5 text-sm font-bold ${
              type === value
                ? "bg-[#0E1A14] text-white dark:bg-[#B2F2BB] dark:text-[#0E1A14]"
                : `${ui.muted} hover:text-[#0E1A14] dark:hover:text-[#F2F5F0]`
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-5 md:grid-cols-4 lg:grid-cols-5">
        {items.map((item, index) => (
          <div key={item.id} className="flex flex-col gap-2.5">
            <div className={`aspect-square overflow-hidden rounded-[14px] ${fallbacks[index % fallbacks.length]}`}>
              {item.type === "image" && item.url ? (
                <img src={item.url} alt="" className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full w-full items-end p-3">
                  <span className="rounded-md bg-[#0E1A14] px-2 py-[3px] text-[10px] font-bold tracking-[0.12em] text-[#B2F2BB] dark:bg-[#B2F2BB] dark:text-[#0E1A14]">
                    VIDEO
                  </span>
                </div>
              )}
            </div>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-[13px] font-bold">{item.name}</p>
                <p className={`text-xs font-medium ${ui.muted}`}>{item.duration}s</p>
              </div>
              <button type="button" className={`${ui.muted} hover:text-[#C2410C]`} title="Delete" onClick={() => setPending(item)}>
                <span className="material-symbols-outlined text-lg">delete</span>
              </button>
            </div>
          </div>
        ))}
      </div>
      {items.length === 0 ? <EmptyNote>Nothing in the library yet.</EmptyNote> : null}
      {uploadOpen ? <UploadModal onClose={() => setUploadOpen(false)} /> : null}
      <DeleteDialog
        open={Boolean(pending)}
        title="Delete this file"
        name={pending?.name ?? ""}
        hint="Playlists that use it will drop this item."
        pending={remove.isPending}
        onClose={() => setPending(null)}
        onConfirm={() => pending && remove.mutate(pending.id)}
      />
    </Page>
  );
}

function UploadModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const client = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"file" | "url">("file");
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");

  const submit = async () => {
    if (submitting) return;
    setSubmitting(true);
    setProgress(0);
    setError("");
    try {
      const form = new FormData();
      if (mode === "file") {
        if (!file) throw new Error("Please select a file");
        form.append("file", file);
      } else {
        form.append("file_url", url);
      }
      form.append("duration", "10");
      await api.uploadMedia(form, setProgress);
      await client.invalidateQueries({ queryKey: ["media"] });
      await client.invalidateQueries({ queryKey: ["dashboard"] });
      toast("Uploaded.");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setSubmitting(false);
    }
  };


  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className={ui.overlay} onClick={onClose} />
      <div className={`${ui.modal} max-w-lg space-y-5`}>
        <div>
          <p className={ui.eyebrow}>Library</p>
          <h3 className="mt-2 text-[28px] font-extrabold leading-8 tracking-[-0.03em]">Upload new media</h3>
        </div>
        <div className="flex gap-2">
          {(["file", "url"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setMode(value)}
              className={`flex-1 rounded-lg py-2 text-sm font-bold ${
                mode === value ? "bg-[#0E1A14] text-white dark:bg-[#B2F2BB] dark:text-[#0E1A14]" : `border border-[#D5D8D2] dark:border-[#3A443C] ${ui.muted}`
              }`}
            >
              {value === "file" ? "File" : "URL"}
            </button>
          ))}
        </div>
        {mode === "file" ? (
          <input
            type="file"
            accept="image/*,video/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="w-full rounded-xl border-2 border-dashed border-[#C4C8C0] p-6 text-sm font-semibold file:mr-4 file:rounded-lg file:border-0 file:bg-[#0E1A14] file:px-3 file:py-1.5 file:text-xs file:font-bold file:text-white dark:border-[#3A443C] dark:file:bg-[#B2F2BB] dark:file:text-[#0E1A14]"
          />
        ) : (
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" className={ui.input} />
        )}
        {error ? <p className={ui.error}>{error}</p> : null}
        {submitting ? (
          <div className="h-1 overflow-hidden rounded-full bg-[#E8EAE6] dark:bg-[#2A322C]">
            <div className="h-full bg-primary transition-all dark:bg-[#B2F2BB]" style={{ width: `${progress}%` }} />
          </div>
        ) : null}
        <div className="flex justify-end gap-3">
          <button type="button" onClick={onClose} className={ui.btnGhost}>
            Cancel
          </button>
          <button type="button" disabled={submitting} onClick={() => void submit()} className={ui.btnPrimary}>
            {submitting ? (progress ? `Uploading ${progress}%` : "Uploading…") : "Upload"}
          </button>
        </div>
      </div>
    </div>
  );
}
