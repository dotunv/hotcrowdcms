"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const TILE_STYLES = [
  {
    surface: "bg-[#B2F2BB] border-[#0E1A14] dark:border-[#F2F5F0]",
    eyebrow: "text-[#045E33]",
    title: "text-[#0E1A14]",
    badge: "bg-[#0E1A14] text-[#B2F2BB]",
  },
  {
    surface: "bg-[#0E1A14] border-[#0E1A14] dark:bg-[#1F2622] dark:border-[#F2F5F0]",
    eyebrow: "text-[#B2F2BB]",
    title: "text-white",
    badge: "bg-[#B2F2BB] text-[#0E1A14]",
  },
  {
    surface: "bg-[#FFD84D] border-[#0E1A14] dark:border-[#F2F5F0]",
    eyebrow: "text-[#0E1A14]",
    title: "text-[#0E1A14]",
    badge: "bg-[#0E1A14] text-[#FFD84D]",
  },
];

const MEDIA_FALLBACKS = [
  "bg-[#B2F2BB]",
  "bg-[#0E1A14] dark:bg-[#1F2622] dark:border dark:border-[#2A322C]",
  "bg-[#FFD84D]",
  "bg-[#F3F4F1] dark:bg-[#2A322C]",
  "bg-[#045E33] dark:bg-[#057A43]",
];

const eyebrow = "text-xs font-semibold uppercase tracking-[0.14em]";
const sectionHead =
  "flex items-baseline justify-between border-b-2 border-[#0E1A14] pb-3.5 dark:border-[#F2F5F0]";
const sectionTitle = "text-lg font-extrabold tracking-[-0.02em] text-[#0E1A14] dark:text-[#F2F5F0]";
const sectionLink = "text-sm font-bold text-primary dark:text-[#B2F2BB]";
const rowLine = "border-b border-[#E8EAE6] dark:border-[#2A322C]";
const ghostButton =
  "rounded-xl border border-[#D5D8D2] px-5 py-3 text-sm font-bold text-[#0E1A14] dark:border-[#3A443C] dark:text-[#F2F5F0]";
const primaryButton =
  "rounded-xl bg-primary px-5 py-3 text-sm font-bold text-white dark:bg-[#B2F2BB] dark:text-[#0E1A14]";

function useGreeting() {
  const [greeting, setGreeting] = useState("");
  useEffect(() => {
    const now = new Date();
    const hour = now.getHours();
    const part = hour < 12 ? "morning" : hour < 18 ? "afternoon" : "evening";
    const day = now.toLocaleDateString(undefined, { weekday: "long" });
    const date = now.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    setGreeting(`${day} ${part} · ${date}`);
  }, []);
  return greeting;
}

export default function DashboardPage() {
  const dash = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const playlists = useQuery({ queryKey: ["playlists"], queryFn: api.playlists });
  const greeting = useGreeting();
  const data = dash.data;
  const empty = data && (data.total_screens === 0 || data.total_media === 0);
  const screens = data?.screens ?? [];
  const media = data?.recent_media ?? [];
  const offline = screens.filter((screen) => !screen.online);
  const unassigned = screens.filter((screen) => screen.online && !screen.playlist_name);
  const attention = [
    ...offline.map((screen) => ({ id: `off-${screen.id}`, tone: "warn", text: `${screen.name} is offline`, href: "/screens" })),
    ...unassigned.map((screen) => ({ id: `idle-${screen.id}`, tone: "warn", text: `${screen.name} has no playlist`, href: "/screens" })),
  ];

  return (
    <div className="h-full overflow-y-auto bg-white font-sans text-[#0E1A14] dark:bg-[#111513] dark:text-[#F2F5F0]">
      <div className="flex flex-col gap-12 px-14 py-12">
        <header className="flex items-end justify-between gap-4">
          <div className="flex flex-col gap-2.5">
            <p className={`${eyebrow} min-h-4 text-primary dark:text-[#B2F2BB]`}>
              {empty ? "Welcome · let's get you on air" : greeting}
            </p>
            <h1 className="text-[44px] font-extrabold leading-[48px] tracking-[-0.035em]">{data?.store_name ?? "Your store"}</h1>
          </div>
          <div className="flex gap-3">
            <Link href="/screens" className={ghostButton}>
              Connect screen
            </Link>
            <Link href="/playlists" className={primaryButton}>
              New playlist
            </Link>
          </div>
        </header>

        {empty ? (
          <EmptyState hasScreens={(data?.total_screens ?? 0) > 0} hasMedia={(data?.total_media ?? 0) > 0} />
        ) : data ? (
          <>
            <section className="flex flex-col gap-7" aria-label="Screens now">
              <div className="flex items-center justify-between gap-4">
                <h2 className="flex flex-wrap items-center gap-3.5 text-[30px] font-extrabold tracking-[-0.03em]">
                  <span>
                    {data.online_screens} of {data.total_screens} screens are
                  </span>
                  <span className="-rotate-2 rounded-[10px] bg-[#B2F2BB] px-3 text-[#045E33] dark:text-[#0E1A14]">live.</span>
                  {data.offline_screens > 0 ? (
                    <span className="text-[#9AA09A] dark:text-[#6B746C]">
                      {data.offline_screens === 1 ? "One needs you." : `${data.offline_screens} need you.`}
                    </span>
                  ) : null}
                </h2>
                {data.last_heartbeat ? (
                  <p className="flex shrink-0 items-center gap-2 text-[13px] font-semibold text-[#6B7280] dark:text-[#9BA59C]">
                    <span className="h-2 w-2 rounded-full bg-primary dark:bg-[#B2F2BB]" />
                    Updated {data.last_heartbeat.slice(11, 16)} UTC
                  </p>
                ) : null}
              </div>
              <div className="grid grid-cols-2 gap-5 lg:grid-cols-4">
                {screens.map((screen, index) => {
                  const tile = TILE_STYLES[index % TILE_STYLES.length];
                  return screen.online ? (
                    <div key={screen.id} className="flex flex-col gap-3.5">
                      <div
                        className={`relative flex h-[145px] flex-col justify-end rounded-2xl border-[3px] p-4 ${tile.surface}`}
                      >
                        <span
                          className={`absolute left-2.5 top-2.5 rounded-md px-2 py-[3px] text-[10px] font-bold tracking-[0.12em] ${tile.badge}`}
                        >
                          LIVE
                        </span>
                        <p className={`text-xs font-bold uppercase tracking-[0.1em] ${tile.eyebrow}`}>Now playing</p>
                        <p className={`line-clamp-2 text-[26px] font-extrabold leading-7 tracking-[-0.03em] ${tile.title}`}>
                          {screen.playlist_name || "No playlist yet"}
                        </p>
                      </div>
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-[15px] font-bold">{screen.name}</p>
                          <p className="text-xs font-bold text-primary dark:text-[#B2F2BB]">Playing</p>
                        </div>
                        <p className="truncate text-[13px] font-medium text-[#6B7280] dark:text-[#9BA59C]">
                          {screen.playlist_name || "Assign a playlist to start"}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div key={screen.id} className="flex flex-col gap-3.5">
                      <div className="flex h-[145px] flex-col items-center justify-center gap-2 rounded-2xl border-[3px] border-dashed border-[#C4C8C0] bg-[#F3F4F1] dark:border-[#3A443C] dark:bg-[#171C19]">
                        <span className="flex h-7 w-7 items-center justify-center rounded-full border-[3px] border-[#9AA09A] dark:border-[#6B746C]">
                          <span className="h-3 w-[3px] bg-[#9AA09A] dark:bg-[#6B746C]" />
                        </span>
                        <p className="text-[15px] font-bold text-[#6B7280] dark:text-[#9BA59C]">Screen is asleep</p>
                      </div>
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-[15px] font-bold">{screen.name}</p>
                          <p className="text-xs font-bold text-[#C2410C] dark:text-[#FB923C]">Offline</p>
                        </div>
                        <p className="truncate text-[13px] font-medium text-[#6B7280] dark:text-[#9BA59C]">
                          {screen.playlist_name || "No playlist"}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Link
                          href="/screens"
                          className="rounded-lg bg-[#0E1A14] px-3 py-1.5 text-xs font-bold text-white dark:bg-[#F2F5F0] dark:text-[#0E1A14]"
                        >
                          Reconnect
                        </Link>
                        <Link
                          href="/screens"
                          className="rounded-lg border border-[#D5D8D2] px-3 py-1.5 text-xs font-bold text-[#0E1A14] dark:border-[#3A443C] dark:text-[#F2F5F0]"
                        >
                          Assign playlist
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            <section
              aria-label="Totals"
              className="grid grid-cols-2 gap-y-4 border-y border-[#E8EAE6] py-6 dark:border-[#2A322C] lg:grid-cols-4"
            >
              {[
                [String(data.total_playlists), "playlists"],
                [String(data.total_media), "files in library"],
                [data.last_publish ? data.last_publish.slice(0, 10) : "Never", "last publish"],
                [String(data.offline_screens), "screens offline"],
              ].map(([value, label]) => (
                <p key={label} className="flex items-baseline gap-2.5">
                  <span className="text-[32px] font-extrabold tracking-[-0.04em]">{value}</span>
                  <span className="text-[13px] font-semibold text-[#6B7280] dark:text-[#9BA59C]">{label}</span>
                </p>
              ))}
            </section>

            <div className="grid gap-14 lg:grid-cols-[1.2fr_1fr]">
              <section>
                <div className={sectionHead}>
                  <h2 className={sectionTitle}>Playlists</h2>
                  <Link href="/playlists" className={sectionLink}>
                    Edit
                  </Link>
                </div>
                {(playlists.data?.results ?? []).slice(0, 5).map((playlist) => (
                  <Link
                    key={playlist.id}
                    href={`/playlists/${playlist.id}`}
                    className={`flex items-center gap-5 py-4 ${rowLine}`}
                  >
                    <span className="flex-1 truncate text-[15px] font-bold">{playlist.name}</span>
                    <span className="w-20 shrink-0 text-xs font-semibold text-[#6B7280] dark:text-[#9BA59C]">
                      {playlist.item_count} {playlist.item_count === 1 ? "item" : "items"}
                    </span>
                    <span className="flex w-20 shrink-0 justify-end">
                      <span
                        className={`rounded-md px-2 py-[3px] text-[11px] font-bold uppercase ${
                          playlist.status === "ACTIVE"
                            ? "bg-[#B2F2BB] text-[#045E33] dark:text-[#0E1A14]"
                            : "bg-[#F3F4F1] text-[#6B7280] dark:bg-[#2A322C] dark:text-[#9BA59C]"
                        }`}
                      >
                        {playlist.status === "ACTIVE" ? "Live" : playlist.status.toLowerCase()}
                      </span>
                    </span>
                  </Link>
                ))}
                {playlists.data && playlists.data.results.length === 0 ? (
                  <p className="py-4 text-sm text-[#6B7280] dark:text-[#9BA59C]">No playlists yet.</p>
                ) : null}
              </section>

              <section>
                <div className={sectionHead}>
                  <h2 className={sectionTitle}>Needs attention</h2>
                </div>
                {attention.map((item) => (
                  <Link key={item.id} href={item.href} className={`flex items-start gap-3.5 py-4 ${rowLine}`}>
                    <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[#C2410C] dark:bg-[#FB923C]" />
                    <span className="text-sm font-bold">{item.text}</span>
                  </Link>
                ))}
                {attention.length === 0 ? (
                  <div className={`flex items-start gap-3.5 py-4 ${rowLine}`}>
                    <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary dark:bg-[#B2F2BB]" />
                    <span className="text-sm font-bold">All screens are online and playing.</span>
                  </div>
                ) : null}
              </section>
            </div>

            <section className="flex flex-col gap-4">
              <div className={sectionHead}>
                <h2 className={sectionTitle}>Recent media</h2>
                <Link href="/library" className={sectionLink}>
                  Open library
                </Link>
              </div>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
                {media.slice(0, 5).map((item, index) => (
                  <Link key={item.id} href="/library" className="flex flex-col gap-2">
                    <div className={`h-[110px] overflow-hidden rounded-[14px] ${MEDIA_FALLBACKS[index % MEDIA_FALLBACKS.length]}`}>
                      {item.type === "image" && item.url ? (
                        <img src={item.url} alt="" className="h-full w-full object-cover" />
                      ) : null}
                    </div>
                    <p className="truncate text-xs font-semibold">{item.name}</p>
                  </Link>
                ))}
              </div>
              {media.length === 0 ? <p className="text-sm text-[#6B7280] dark:text-[#9BA59C]">Nothing uploaded yet.</p> : null}
            </section>
          </>
        ) : null}
      </div>
    </div>
  );
}

function EmptyState({ hasScreens, hasMedia }: { hasScreens: boolean; hasMedia: boolean }) {
  const steps = [
    {
      title: "Connect a screen",
      body: "Open the player on any TV browser and type in the pairing code.",
      cta: "Connect screen",
      href: "/screens",
      done: hasScreens,
    },
    {
      title: "Add your media",
      body: "Drop in photos and videos, or import from Instagram.",
      cta: "Open library",
      href: "/library",
      done: hasMedia,
    },
    {
      title: "Publish a playlist",
      body: "Pick what plays, set a schedule, and send it to your screens.",
      cta: "New playlist",
      href: "/playlists",
      done: false,
    },
  ];
  const current = steps.findIndex((step) => !step.done);

  return (
    <section className="flex flex-col gap-16 lg:flex-row lg:items-stretch">
      <div className="flex flex-1 flex-col justify-center gap-10">
        <h2 className="text-[44px] font-extrabold leading-[48px] tracking-[-0.04em]">
          Three steps to
          <br />
          <span className="mr-3.5 inline-block -rotate-2 rounded-xl bg-[#B2F2BB] px-3.5 leading-[52px] text-[#045E33] dark:text-[#0E1A14]">
            your first
          </span>
          screen.
        </h2>
        <ol>
          {steps.map((step, index) => {
            const active = index === current;
            return (
              <li
                key={step.title}
                className={`flex items-start gap-6 py-6 ${
                  index === 0
                    ? "border-t-2 border-[#0E1A14] dark:border-[#F2F5F0]"
                    : "border-t border-[#E8EAE6] dark:border-[#2A322C]"
                } ${index === steps.length - 1 ? "border-b border-b-[#E8EAE6] dark:border-b-[#2A322C]" : ""}`}
              >
                <span
                  className={`w-12 shrink-0 text-[32px] font-extrabold tracking-[-0.04em] ${
                    active ? "text-primary dark:text-[#B2F2BB]" : "text-[#9AA09A] dark:text-[#6B746C]"
                  }`}
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div className="flex flex-1 flex-col gap-1.5">
                  <p className="text-xl font-extrabold tracking-[-0.02em]">
                    {step.title}
                    {step.done ? <span className="ml-3 align-middle text-xs font-bold uppercase text-primary dark:text-[#B2F2BB]">Done</span> : null}
                  </p>
                  <p className="text-[15px] font-medium leading-[22px] text-[#6B7280] dark:text-[#9BA59C]">{step.body}</p>
                </div>
                <Link
                  href={step.href}
                  className={`shrink-0 rounded-[10px] px-4 py-2.5 text-sm font-bold ${
                    active
                      ? "bg-primary text-white dark:bg-[#B2F2BB] dark:text-[#0E1A14]"
                      : "border border-[#D5D8D2] text-[#0E1A14] dark:border-[#3A443C] dark:text-[#F2F5F0]"
                  }`}
                >
                  {step.cta}
                </Link>
              </li>
            );
          })}
        </ol>
      </div>
      <div className="flex shrink-0 flex-col justify-center gap-5 lg:w-[400px]">
        <div className="flex h-60 flex-col items-center justify-center gap-3 rounded-[20px] border-[6px] border-[#0E1A14] bg-[#0E1A14] shadow-[12px_12px_0_#B2F2BB] dark:border-[#1F2622] dark:bg-[#1F2622]">
          <p className="text-xs font-bold tracking-[0.16em] text-[#B2F2BB]">PAIRING CODE</p>
          <p className="text-[56px] font-extrabold leading-[60px] tracking-[0.08em] text-white">K7P·4QX</p>
          <p className="text-[13px] font-medium text-[#9AA09A]">Example. Your real code shows on the TV</p>
        </div>
        <p className="pt-3 text-sm font-semibold leading-5 text-[#6B7280] dark:text-[#9BA59C]">
          Takes about a minute. Your TV just needs a web browser.
        </p>
      </div>
    </section>
  );
}
