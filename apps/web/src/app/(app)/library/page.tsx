"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { DeleteDialog } from "@/components/delete-dialog";
import { api } from "@/lib/api";
import type { MediaItem } from "@/lib/types";

export default function LibraryPage() {
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
    },
  });

  return (
    <div className="p-8 h-full overflow-y-auto space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold">Library</h1>
          <p className="text-gray-500 mt-1">Images and videos that can play on a screen.</p>
        </div>
        <button type="button" onClick={() => setUploadOpen(true)} className="px-4 py-2 bg-primary text-white text-sm font-bold rounded-xl">
          Upload
        </button>
      </div>
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
            className={`px-3 py-1.5 rounded-lg text-sm font-bold ${type === value ? "bg-gray-900 text-white dark:bg-white dark:text-gray-900" : "text-gray-500"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {(media.data?.results ?? []).map((item) => (
          <div key={item.id} className="bg-white dark:bg-surface-dark rounded-xl overflow-hidden border">
            <div className="aspect-square bg-gray-100 dark:bg-gray-800">
              {item.type === "image" && item.url ? (
                <img src={item.url} alt="" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-400">VID</div>
              )}
            </div>
            <div className="p-3 flex justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm font-semibold truncate">{item.name}</p>
                <p className="text-xs text-gray-500">{item.duration}s</p>
              </div>
              <button type="button" className="text-gray-400 hover:text-red-600" onClick={() => setPending(item)}>
                <span className="material-symbols-outlined text-lg">delete</span>
              </button>
            </div>
          </div>
        ))}
      </div>
      {(media.data?.results ?? []).length === 0 ? <p className="text-center text-gray-500 py-16">Nothing in the library</p> : null}
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
    </div>
  );
}

function UploadModal({ onClose }: { onClose: () => void }) {
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
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-white dark:bg-surface-dark w-full max-w-lg rounded-2xl p-8 space-y-4">
        <h3 className="text-xl font-bold">Upload new media</h3>
        <div className="flex gap-2">
          <button type="button" onClick={() => setMode("file")} className={`flex-1 py-2 rounded-lg text-sm font-medium ${mode === "file" ? "bg-gray-100 dark:bg-gray-800" : ""}`}>
            File
          </button>
          <button type="button" onClick={() => setMode("url")} className={`flex-1 py-2 rounded-lg text-sm font-medium ${mode === "url" ? "bg-gray-100 dark:bg-gray-800" : ""}`}>
            URL
          </button>
        </div>
        {mode === "file" ? (
          <input type="file" accept="image/*,video/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        ) : (
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" className="w-full px-3 py-2 rounded-xl border" />
        )}
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        {submitting ? (
          <div className="h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
            <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
          </div>
        ) : null}
        <div className="flex justify-end gap-3">
          <button type="button" onClick={onClose} className="px-4 py-2 border rounded-xl">
            Cancel
          </button>
          <button type="button" disabled={submitting} onClick={() => void submit()} className="px-6 py-2 bg-primary text-white rounded-xl font-bold disabled:opacity-50">
            {submitting ? (progress ? `Uploading ${progress}%` : "Uploading…") : "Upload"}
          </button>
        </div>
      </div>
    </div>
  );
}
