"use client";

import { ui } from "@/components/ui";

export function DeleteDialog({
  open,
  title,
  name,
  hint,
  onClose,
  onConfirm,
  pending,
}: {
  open: boolean;
  title: string;
  name: string;
  hint: string;
  onClose: () => void;
  onConfirm: () => void;
  pending?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className={ui.overlay} onClick={onClose} />
      <div className={`${ui.modal} max-w-md`}>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#C2410C] dark:text-[#FB923C]">Can&apos;t be undone</p>
        <h3 className="mt-2 text-[28px] font-extrabold leading-8 tracking-[-0.03em]">{title}</h3>
        {name ? (
          <p className="mt-4 inline-block -rotate-1 rounded-lg bg-[#FFD84D] px-3 py-1 text-sm font-extrabold text-[#0E1A14]">{name}</p>
        ) : null}
        <p className={`mt-4 text-[15px] font-medium leading-[22px] ${ui.muted}`}>{hint}</p>
        <div className="mt-8 flex gap-3">
          <button type="button" onClick={onClose} className={`${ui.btnGhost} flex-1`}>
            Cancel
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={onConfirm}
            className="flex-1 rounded-xl bg-[#C2410C] px-5 py-3 text-sm font-bold text-white disabled:opacity-50 dark:bg-[#FB923C] dark:text-[#0E1A14]"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
