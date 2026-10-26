import type { ReactNode } from "react";

export const ui = {
  eyebrow: "text-xs font-semibold uppercase tracking-[0.14em] text-primary dark:text-[#B2F2BB]",
  muted: "text-[#6B7280] dark:text-[#9BA59C]",
  btnPrimary:
    "rounded-xl bg-primary px-5 py-3 text-sm font-bold text-white disabled:opacity-50 dark:bg-[#B2F2BB] dark:text-[#0E1A14]",
  btnGhost:
    "rounded-xl border border-[#D5D8D2] px-5 py-3 text-sm font-bold text-[#0E1A14] disabled:opacity-50 dark:border-[#3A443C] dark:text-[#F2F5F0]",
  btnSmall:
    "rounded-lg border border-[#D5D8D2] px-3 py-1.5 text-xs font-bold text-[#0E1A14] dark:border-[#3A443C] dark:text-[#F2F5F0]",
  btnDanger: "text-sm font-bold text-[#C2410C] dark:text-[#FB923C]",
  input:
    "w-full rounded-xl border border-[#D5D8D2] bg-transparent px-4 py-2.5 text-sm font-medium text-[#0E1A14] placeholder:text-[#9AA09A] focus:border-primary focus:outline-none dark:border-[#3A443C] dark:text-[#F2F5F0] dark:placeholder:text-[#6B746C] dark:focus:border-[#B2F2BB]",
  sectionHead: "flex items-baseline justify-between border-b-2 border-[#0E1A14] pb-3.5 dark:border-[#F2F5F0]",
  sectionTitle: "text-lg font-extrabold tracking-[-0.02em]",
  sectionLink: "text-sm font-bold text-primary dark:text-[#B2F2BB]",
  row: "border-b border-[#E8EAE6] dark:border-[#2A322C]",
  overlay: "absolute inset-0 bg-[#0E1A14]/60",
  modal:
    "relative w-full rounded-[20px] border border-[#E8EAE6] bg-white p-8 shadow-[12px_12px_0_#B2F2BB] dark:border-[#2A322C] dark:bg-[#1F2622] dark:shadow-none",
  surface: "rounded-2xl border border-[#E8EAE6] bg-white dark:border-[#2A322C] dark:bg-[#171C19]",
  error: "text-sm font-semibold text-[#C2410C] dark:text-[#FB923C]",
};

/** Page frame shared by every screen: scroll area, eyebrow, display title, optional actions. */
export function Page({
  eyebrow,
  title,
  subtitle,
  actions,
  narrow,
  children,
}: {
  eyebrow?: string;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  narrow?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="h-full overflow-y-auto bg-white font-sans text-[#0E1A14] dark:bg-[#111513] dark:text-[#F2F5F0]">
      <div className={`flex flex-col gap-10 px-14 py-12 ${narrow ? "max-w-[880px]" : ""}`}>
        <header className="flex items-end justify-between gap-4">
          <div className="flex flex-col gap-2.5">
            {eyebrow ? <p className={ui.eyebrow}>{eyebrow}</p> : null}
            <h1 className="text-[44px] font-extrabold leading-[48px] tracking-[-0.035em]">{title}</h1>
            {subtitle ? <p className={`max-w-xl text-[15px] font-medium leading-[22px] ${ui.muted}`}>{subtitle}</p> : null}
          </div>
          {actions ? <div className="flex shrink-0 gap-3">{actions}</div> : null}
        </header>
        {children}
      </div>
    </div>
  );
}

export function Section({ title, link, children }: { title: string; link?: ReactNode; children: ReactNode }) {
  return (
    <section>
      <div className={ui.sectionHead}>
        <h2 className={ui.sectionTitle}>{title}</h2>
        {link}
      </div>
      {children}
    </section>
  );
}

export function StatStrip({ items }: { items: [string, string | number][] }) {
  return (
    <div className="grid grid-cols-2 gap-y-4 border-y border-[#E8EAE6] py-6 dark:border-[#2A322C] sm:grid-cols-3">
      {items.map(([label, value]) => (
        <p key={label} className="flex items-baseline gap-2.5">
          <span className="text-[32px] font-extrabold tracking-[-0.04em]">{value}</span>
          <span className={`text-[13px] font-semibold ${ui.muted}`}>{label}</span>
        </p>
      ))}
    </div>
  );
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-2xl border-[3px] border-dashed border-[#C4C8C0] bg-[#F3F4F1] px-8 py-14 text-center text-[15px] font-bold text-[#6B7280] dark:border-[#3A443C] dark:bg-[#171C19] dark:text-[#9BA59C]">
      {children}
    </div>
  );
}

const STATUS_TONE: Record<string, string> = {
  ACTIVE: "bg-[#B2F2BB] text-[#045E33] dark:text-[#0E1A14]",
  PUBLISHED: "bg-[#B2F2BB] text-[#045E33] dark:text-[#0E1A14]",
  SCHEDULED: "bg-[#FFD84D] text-[#0E1A14]",
};

export function StatusBadge({ status }: { status: string }) {
  const key = status.toUpperCase();
  const tone = STATUS_TONE[key] ?? "bg-[#F3F4F1] text-[#6B7280] dark:bg-[#2A322C] dark:text-[#9BA59C]";
  return (
    <span className={`rounded-md px-2 py-[3px] text-[11px] font-bold uppercase tracking-[0.04em] ${tone}`}>
      {key === "ACTIVE" ? "Live" : status.toLowerCase()}
    </span>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[13px] font-bold">{label}</span>
      {children}
      {hint ? <span className={`text-xs font-medium ${ui.muted}`}>{hint}</span> : null}
    </label>
  );
}
