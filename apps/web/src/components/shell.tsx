"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { api } from "@/lib/api";

function toggleTheme() {
  const next = !document.documentElement.classList.contains("dark");
  document.documentElement.classList.toggle("dark", next);
  localStorage.setItem("theme", next ? "dark" : "light");
}

const NAV = [
  { href: "/", label: "Dashboard", icon: "dashboard", match: (p: string) => p === "/" },
  { href: "/screens", label: "Screens", icon: "monitor", match: (p: string) => p.startsWith("/screens") },
  { href: "/playlists", label: "Playlists", icon: "featured_play_list", match: (p: string) => p.startsWith("/playlists") },
  { href: "/library", label: "Library", icon: "photo_library", match: (p: string) => p.startsWith("/library") },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const client = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });
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
    <div className="flex h-screen bg-background-light dark:bg-background-dark font-sans">
      <aside className="w-64 bg-white dark:bg-surface-dark border-r border-border-light dark:border-border-dark flex flex-col fixed inset-y-0 z-20">
        <div className="h-16 flex items-center px-6 border-b border-border-light dark:border-border-dark">
          <Link href="/" className="font-bold text-lg text-gray-900 dark:text-white">
            HotCrowd
          </Link>
        </div>
        <div className="p-4">
          <div className="w-full flex items-center gap-3 px-3 py-2 bg-gray-50 dark:bg-gray-800 rounded-xl border border-border-light dark:border-border-dark">
            <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">
              {me.data.store.initials}
            </div>
            <span className="text-sm font-semibold text-gray-700 dark:text-gray-200 truncate">
              {me.data.store.business_name || me.data.username}
            </span>
          </div>
        </div>
        <nav className="flex-1 px-4 space-y-1">
          <p className="px-2 text-xs font-bold text-gray-400 uppercase tracking-wider mt-4 mb-2">Main</p>
          {NAV.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium ${
                  active ? "bg-primary/10 text-primary" : "text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800"
                }`}
              >
                <span className="material-symbols-outlined">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
          <p className="px-2 text-xs font-bold text-gray-400 uppercase tracking-wider mt-6 mb-2">Settings</p>
          <Link
            href="/store"
            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium ${
              pathname.startsWith("/store") ? "bg-primary/10 text-primary" : "text-gray-600 hover:bg-gray-50 dark:text-gray-400"
            }`}
          >
            <span className="material-symbols-outlined">settings</span>
            Store
          </Link>
          <Link
            href="/help"
            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium ${
              pathname.startsWith("/help") ? "bg-primary/10 text-primary" : "text-gray-600 hover:bg-gray-50 dark:text-gray-400"
            }`}
          >
            <span className="material-symbols-outlined">help</span>
            Help
          </Link>
        </nav>
        <div className="p-4 border-t border-border-light dark:border-border-dark flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-gray-900 dark:text-white truncate">{me.data.username}</p>
            <p className="text-xs text-gray-500 truncate">{me.data.email}</p>
          </div>
          <button type="button" onClick={toggleTheme} className="p-2 rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800" title="Toggle theme">
            <span className="material-symbols-outlined text-xl dark:hidden">dark_mode</span>
            <span className="material-symbols-outlined text-xl hidden dark:inline">light_mode</span>
          </button>
          <button type="button" onClick={() => logout.mutate()} className="text-gray-400 hover:text-red-500" title="Log out">
            <span className="material-symbols-outlined">logout</span>
          </button>
        </div>
      </aside>
      <main className="flex-1 ml-64 h-screen overflow-hidden bg-background-light dark:bg-background-dark">{children}</main>
    </div>
  );
}
