"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import type { StoreSettings } from "@/lib/types";
import { useToast } from "@/components/toast";

const ZONES = [
  "UTC",
  "Africa/Lagos",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Paris",
  "Asia/Dubai",
];

const INPUT = "mt-1 w-full rounded-xl border border-border-light px-3 py-2 dark:border-border-dark dark:bg-gray-900";

const empty: StoreSettings = {
  id: 0,
  business_name: "",
  initials: "HC",
  description: "",
  phone_number: "",
  timezone: "UTC",
  branding_color: "#057A43",
  default_image_duration: 10,
  transition_effect: "fade",
  mute_by_default: false,
  default_volume: 75,
  fallback_type: "brand_logo",
  fallback_logo: "",
  logo_url: null,
};

export default function StorePage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["store"], queryFn: api.store });
  const [form, setForm] = useState<StoreSettings>(empty);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const save = useMutation({
    mutationFn: () =>
      api.patchStore({
        business_name: form.business_name,
        timezone: form.timezone,
        description: form.description,
        phone_number: form.phone_number,
        branding_color: form.branding_color,
        default_image_duration: form.default_image_duration,
        transition_effect: form.transition_effect,
        mute_by_default: form.mute_by_default,
        default_volume: form.default_volume,
        fallback_type: form.fallback_type,
        fallback_logo: form.fallback_logo,
      }),
    onSuccess: (next) => {
      setForm(next);
      void queryClient.invalidateQueries({ queryKey: ["store"] });
      void queryClient.invalidateQueries({ queryKey: ["me"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast("Store saved.");
    },
  });

  const logo = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return api.uploadLogo(body);
    },
    onSuccess: (next) => {
      setForm(next);
      void queryClient.invalidateQueries({ queryKey: ["me"] });
      toast("Logo updated.");
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <div className="h-full overflow-y-auto">
      <form onSubmit={onSubmit} className="mx-auto max-w-2xl space-y-6 p-8 pb-24">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Store</h1>
            <p className="mt-1 text-sm text-gray-500">Branding and playback defaults for this shop.</p>
          </div>
          <button className="rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-white" type="submit">
            {save.isPending ? "Saving…" : "Save store"}
          </button>
        </div>
        <section className="space-y-4 rounded-2xl border bg-white p-6 dark:border-border-dark dark:bg-surface-dark">
          <h2 className="font-bold">Business</h2>
          <div className="flex items-center gap-4">
            <div className="h-16 w-16 overflow-hidden rounded-2xl bg-primary/10">
              {form.logo_url ? (
                <img src={form.logo_url} alt="" className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full items-center justify-center font-bold text-primary">{form.initials}</div>
              )}
            </div>
            <label className="text-sm font-semibold text-primary">
              Upload logo
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) logo.mutate(file);
                }}
              />
            </label>
          </div>
          <Field label="Name">
            <input className={INPUT} value={form.business_name} onChange={(e) => setForm({ ...form, business_name: e.target.value })} />
          </Field>
          <Field label="Phone">
            <input className={INPUT} value={form.phone_number} onChange={(e) => setForm({ ...form, phone_number: e.target.value })} />
          </Field>
          <Field label="Timezone">
            <input className={INPUT} list="zones" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
            <datalist id="zones">
              {ZONES.map((zone) => (
                <option key={zone} value={zone} />
              ))}
            </datalist>
          </Field>
          <Field label="Brand color">
            <input type="color" value={form.branding_color} onChange={(e) => setForm({ ...form, branding_color: e.target.value })} />
          </Field>
          <Field label="Description">
            <textarea className={INPUT} rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
        </section>
        <section className="space-y-4 rounded-2xl border bg-white p-6 dark:border-border-dark dark:bg-surface-dark">
          <h2 className="font-bold">Playback defaults</h2>
          <Field label="Image duration (seconds)">
            <input
              type="number"
              min={1}
              className={INPUT}
              value={form.default_image_duration}
              onChange={(e) => setForm({ ...form, default_image_duration: Number(e.target.value) })}
            />
          </Field>
          <Field label="Transition">
            <select className={INPUT} value={form.transition_effect} onChange={(e) => setForm({ ...form, transition_effect: e.target.value })}>
              <option value="fade">Fade</option>
              <option value="slide">Slide</option>
              <option value="zoom">Zoom</option>
              <option value="none">None</option>
            </select>
          </Field>
          <Field label="Default volume">
            <input
              type="range"
              min={0}
              max={100}
              value={form.default_volume}
              onChange={(e) => setForm({ ...form, default_volume: Number(e.target.value) })}
            />
            <span className="text-sm text-gray-500">{form.default_volume}%</span>
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.mute_by_default} onChange={(e) => setForm({ ...form, mute_by_default: e.target.checked })} />
            Mute videos by default
          </label>
          <Field label="When a playlist is empty">
            <select className={INPUT} value={form.fallback_type} onChange={(e) => setForm({ ...form, fallback_type: e.target.value })}>
              <option value="brand_logo">Brand logo</option>
              <option value="custom_media">Custom URL</option>
              <option value="black_screen">Black screen</option>
            </select>
          </Field>
          {form.fallback_type === "custom_media" ? (
            <Field label="Fallback media URL">
              <input className={INPUT} value={form.fallback_logo} onChange={(e) => setForm({ ...form, fallback_logo: e.target.value })} />
            </Field>
          ) : null}
        </section>
        {save.isError ? <p className="text-sm text-red-600">{(save.error as Error).message}</p> : null}
        <button className="rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-white" type="submit">
          Save store
        </button>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm font-medium">
      {label}
      {children}
    </label>
  );
}
