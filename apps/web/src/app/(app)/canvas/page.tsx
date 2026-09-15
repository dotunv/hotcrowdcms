"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function CanvasListPage() {
  const router = useRouter();
  const list = useQuery({ queryKey: ["layouts"], queryFn: api.layouts });
  const create = useMutation({
    mutationFn: () => api.createLayout("Untitled layout"),
    onSuccess: (layout) => router.push(`/canvas/${layout.id}`),
  });

  return (
    <div className="h-full overflow-y-auto p-8 space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold">Canvas</h1>
          <p className="mt-1 text-gray-500">Design a 1920×1080 board, publish it, then drop it into a playlist.</p>
        </div>
        <button type="button" onClick={() => create.mutate()} className="rounded-xl bg-primary px-4 py-2 text-sm font-bold text-white">
          New layout
        </button>
      </div>
      <div className="grid gap-4">
        {(list.data?.results ?? []).map((layout) => (
          <div key={layout.id} className="flex items-center justify-between rounded-2xl border bg-white p-5 dark:bg-surface-dark">
            <div>
              <Link href={`/canvas/${layout.id}`} className="text-lg font-bold hover:text-primary">
                {layout.name}
              </Link>
              <p className="text-sm text-gray-500">{layout.status.toLowerCase()}</p>
            </div>
            <Link href={`/canvas/${layout.id}`} className="rounded-xl border px-3 py-2 text-sm font-bold">
              Edit
            </Link>
          </div>
        ))}
        {(list.data?.results ?? []).length === 0 ? (
          <div className="rounded-2xl border border-dashed p-12 text-center text-sm text-gray-500">No layouts yet.</div>
        ) : null}
      </div>
    </div>
  );
}
