"use client";

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
      <div className="absolute inset-0 bg-gray-900/50" onClick={onClose} />
      <div className="relative bg-white dark:bg-surface-dark w-full max-w-md rounded-2xl p-6 border border-border-light dark:border-border-dark">
        <div className="flex items-center justify-center w-12 h-12 mx-auto mb-4 rounded-full bg-red-50 dark:bg-red-900/20">
          <span className="material-symbols-outlined text-red-600">delete</span>
        </div>
        <h3 className="text-lg font-bold text-gray-900 dark:text-white text-center">{title}</h3>
        {name ? <p className="text-sm font-semibold text-center mt-2 text-gray-900 dark:text-white">{name}</p> : null}
        <p className="text-sm text-gray-500 text-center mt-2">{hint}</p>
        <div className="flex gap-3 mt-6">
          <button type="button" onClick={onClose} className="flex-1 px-4 py-2.5 text-sm font-bold border rounded-xl">
            Cancel
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={onConfirm}
            className="flex-1 px-4 py-2.5 text-sm font-bold text-white bg-red-600 rounded-xl disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
