"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { EmptyNote, Page, StatusBadge, ui } from "@/components/ui";

export default function CanvasListPage() {
  const router = useRouter();
  const list = useQuery({ queryKey: ["layouts"], queryFn: api.layouts });
  const create = useMutation({
    mutationFn: () => api.createLayout("Untitled layout"),
    onSuccess: (layout) => router.push(`/canvas/${layout.id}`),
  });

  return (
    <Page
      eyebrow="Design"
      title="Canvas"
      subtitle="Design a 1920×1080 board, publish it, then drop it into a playlist."
      actions={
        <button type="button" onClick={() => create.mutate()} className={ui.btnPrimary}>
          New layout
        </button>
      }
    >
      <section>
        <div className={ui.sectionHead}>
          <h2 className={ui.sectionTitle}>Layouts</h2>
        </div>
        {(list.data?.results ?? []).map((layout) => (
          <div key={layout.id} className={`flex items-center gap-5 py-4 ${ui.row}`}>
            <Link href={`/canvas/${layout.id}`} className="min-w-0 flex-1 truncate text-[17px] font-extrabold tracking-[-0.02em] hover:text-primary dark:hover:text-[#B2F2BB]">
              {layout.name}
            </Link>
            <span className="flex w-24 shrink-0 justify-end">
              <StatusBadge status={layout.status} />
            </span>
            <Link href={`/canvas/${layout.id}`} className={ui.btnSmall}>
              Edit
            </Link>
          </div>
        ))}
        {(list.data?.results ?? []).length === 0 ? (
          <div className="pt-6">
            <EmptyNote>No layouts yet.</EmptyNote>
          </div>
        ) : null}
      </section>
    </Page>
  );
}
