"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast";

function toggleTheme() {
  const next = !document.documentElement.classList.contains("dark");
  document.documentElement.classList.toggle("dark", next);
  localStorage.setItem("theme", next ? "dark" : "light");
}

const NAV = [
  { href: "/", label: "Dashboard", match: (p: string) => p === "/" },
  { href: "/screens", label: "Screens", match: (p: string) => p.startsWith("/screens") },
  { href: "/playlists", label: "Playlists", match: (p: string) => p.startsWith("/playlists") },
  { href: "/library", label: "Library", match: (p: string) => p.startsWith("/library") },
  { href: "/canvas", label: "Canvas", match: (p: string) => p.startsWith("/canvas") },
  { href: "/instagram", label: "Instagram", match: (p: string) => p.startsWith("/instagram") },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const client = useQueryClient();
  const toast = useToast();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });
  const select = useMutation({
    mutationFn: (id: number) => api.selectStore(id),
    onSuccess: () => {
      void client.invalidateQueries();
    },
  });
  const createStore = useMutation({
    mutationFn: () => api.createStore("New location"),
    onSuccess: () => void client.invalidateQueries(),
    onError: (error: Error) => toast(error.message),
  });
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      client.clear();
      router.replace("/login");
    },
  });

  useEffect(() => {
    if (me.isError) router.replace("/login");
  }, [me.isError, router]);

  if (me.isLoading) {
    return <div className="min-h-screen bg-background-light dark:bg-background-dark" />;
  }
  if (!me.data) return null;

  return (
    <div className="flex h-screen bg-white font-sans dark:bg-[#111513]">
      <aside className="fixed inset-y-0 z-20 flex w-60 flex-col justify-between border-r border-[#E8EAE6] bg-white px-6 py-8 dark:border-[#2A322C] dark:bg-[#111513]">
        <div className="flex min-h-0 flex-col gap-8">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="h-7 w-7 rounded-lg bg-primary dark:bg-[#B2F2BB]" />
            <span className="text-lg font-extrabold tracking-[-0.02em] text-[#0E1A14] dark:text-[#F2F5F0]">Hot Crowd</span>
          </Link>
          <div className="flex flex-col gap-1.5">
            <select
              className="w-full rounded-[10px] border border-[#D5D8D2] bg-transparent px-3 py-2 text-sm font-semibold text-[#0E1A14] dark:border-[#3A443C] dark:text-[#F2F5F0] dark:[&>option]:bg-[#111513]"
              value={me.data.store.id}
              onChange={(event) => select.mutate(Number(event.target.value))}
            >
              {(me.data.stores ?? [me.data.store]).map((store) => (
                <option key={store.id} value={store.id}>
                  {store.business_name || store.initials}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="px-1 text-left text-xs font-bold text-primary dark:text-[#B2F2BB]"
              onClick={() => createStore.mutate()}
            >
              {me.data.plan === "pro" ? "Add another store" : "Add a store (Pro)"}
            </button>
          </div>
          <nav className="flex flex-col gap-1">
            {NAV.map((item) => (
              <NavLink key={item.href} href={item.href} label={item.label} active={item.match(pathname)} />
            ))}
          </nav>
        </div>
        <div className="flex flex-col gap-4">
          <nav className="flex flex-col gap-1">
            <NavLink href="/store" label="Store" active={pathname.startsWith("/store")} />
            <NavLink href="/billing" label="Billing" active={pathname.startsWith("/billing")} />
            <NavLink href="/help" label="Help" active={pathname.startsWith("/help")} />
          </nav>
          <div className="flex items-center gap-2 border-t border-[#E8EAE6] pt-4 dark:border-[#2A322C]">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-bold text-[#0E1A14] dark:text-[#F2F5F0]">{me.data.username}</p>
              <p className="truncate text-xs font-medium text-[#6B7280] dark:text-[#9BA59C]">
                {me.data.plan === "pro" ? "Pro" : "Starter"} · {me.data.email}
              </p>
            </div>
            <button
              type="button"
              onClick={toggleTheme}
              className="rounded-lg p-1.5 text-[#6B7280] hover:bg-[#F3F4F1] dark:text-[#9BA59C] dark:hover:bg-[#1F2622]"
              title="Toggle theme"
            >
              <span className="material-symbols-outlined text-xl dark:hidden">dark_mode</span>
              <span className="material-symbols-outlined hidden text-xl dark:inline">light_mode</span>
            </button>
            <button
              type="button"
              onClick={() => logout.mutate()}
              className="rounded-lg p-1.5 text-[#6B7280] hover:text-red-500 dark:text-[#9BA59C]"
              title="Log out"
            >
              <span className="material-symbols-outlined text-xl">logout</span>
            </button>
          </div>
        </div>
      </aside>
      <main className="ml-60 h-screen flex-1 overflow-hidden bg-white dark:bg-[#111513]">{children}</main>
    </div>
  );
}

function NavLink({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-2.5 rounded-[10px] py-2.5 pr-3 text-sm ${
        active
          ? "bg-[#0E1A14] pl-3 font-bold text-white dark:bg-[#B2F2BB] dark:text-[#0E1A14]"
          : "pl-7 font-semibold text-[#6B7280] hover:text-[#0E1A14] dark:text-[#9BA59C] dark:hover:text-[#F2F5F0]"
      }`}
    >
      {active ? <span className="h-1.5 w-1.5 rounded-full bg-[#B2F2BB] dark:bg-[#0E1A14]" /> : null}
      {label}
    </Link>
  );
}
