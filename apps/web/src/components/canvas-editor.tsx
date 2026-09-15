"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { StoreLayout } from "@/lib/types";
import { useToast } from "@/components/toast";

type El = NonNullable<StoreLayout["layout_data"]["elements"]>[number];

const SCALE = 0.36;

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

export function CanvasEditor({ layoutId }: { layoutId: string }) {
  const toast = useToast();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["layout", layoutId], queryFn: () => api.layout(layoutId) });
  const media = useQuery({ queryKey: ["media", ""], queryFn: () => api.media("") });
  const [name, setName] = useState("");
  const [data, setData] = useState<StoreLayout["layout_data"]>({ background: { color: "#111827" }, elements: [] });
  const [selected, setSelected] = useState<string | null>(null);
  const [drag, setDrag] = useState<{ id: string; dx: number; dy: number } | null>(null);

  useEffect(() => {
    if (!query.data) return;
    setName(query.data.name);
    setData(query.data.layout_data || { background: { color: "#111827" }, elements: [] });
  }, [query.data]);

  const save = useMutation({
    mutationFn: () => api.patchLayout(layoutId, { name, layout_data: data }),
    onSuccess: () => toast("Layout saved."),
  });
  const publish = useMutation({
    mutationFn: async () => {
      await api.patchLayout(layoutId, { name, layout_data: data });
      return api.publishLayout(layoutId);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["media"] });
      toast("Published to the library.");
    },
  });

  const elements = data.elements ?? [];
  const current = elements.find((el) => el.id === selected);

  function update(id: string, patch: Partial<El>) {
    setData({
      ...data,
      elements: elements.map((el) => (el.id === id ? { ...el, ...patch } : el)),
    });
  }

  function add(type: string) {
    const el: El = {
      id: uid(),
      type,
      x: 200,
      y: 200,
      width: type === "text" ? 800 : 400,
      height: type === "text" ? 140 : 240,
      text: "New text",
      fontSize: 64,
      color: "#ffffff",
      fill: "#057A43",
    };
    setData({ ...data, elements: [...elements, el] });
    setSelected(el.id);
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-16 items-center justify-between border-b bg-white px-4 dark:bg-surface-dark">
        <div className="flex items-center gap-3">
          <Link href="/canvas" className="text-sm text-gray-500">
            Canvas
          </Link>
          <input value={name} onChange={(e) => setName(e.target.value)} className="bg-transparent font-semibold outline-none" />
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => save.mutate()} className="rounded-lg px-3 py-1.5 text-sm">
            Save
          </button>
          <button type="button" onClick={() => publish.mutate()} className="rounded-lg bg-primary px-4 py-1.5 text-sm font-bold text-white">
            Publish to library
          </button>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <aside className="w-56 space-y-2 border-r bg-white p-3 dark:bg-surface-dark">
          <button type="button" className="w-full rounded-xl border px-3 py-2 text-sm" onClick={() => add("text")}>
            Add text
          </button>
          <button type="button" className="w-full rounded-xl border px-3 py-2 text-sm" onClick={() => add("rect")}>
            Add block
          </button>
          <p className="pt-2 text-xs font-bold uppercase text-gray-400">Library image</p>
          <div className="max-h-64 space-y-2 overflow-y-auto">
            {(media.data?.results ?? [])
              .filter((item) => item.type === "image")
              .map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="block w-full truncate rounded-lg border px-2 py-1 text-left text-xs"
                  onClick={() => {
                    const el: El = {
                      id: uid(),
                      type: "image",
                      x: 240,
                      y: 240,
                      width: 640,
                      height: 360,
                      src: item.url || "",
                    };
                    setData({ ...data, elements: [...elements, el] });
                    setSelected(el.id);
                  }}
                >
                  {item.name}
                </button>
              ))}
          </div>
        </aside>
        <section className="flex flex-1 items-center justify-center overflow-auto bg-gray-200 p-6 dark:bg-black">
          <div
            className="relative shadow-2xl"
            style={{
              width: (query.data?.canvas_width ?? 1920) * SCALE,
              height: (query.data?.canvas_height ?? 1080) * SCALE,
              background: data.background?.color || "#111827",
            }}
            onPointerMove={(event) => {
              if (!drag) return;
              const bounds = event.currentTarget.getBoundingClientRect();
              update(drag.id, {
                x: (event.clientX - bounds.left) / SCALE - drag.dx,
                y: (event.clientY - bounds.top) / SCALE - drag.dy,
              });
            }}
            onPointerUp={() => setDrag(null)}
          >
            {elements.map((el) => (
              <div
                key={el.id}
                onPointerDown={(event) => {
                  event.stopPropagation();
                  setSelected(el.id);
                  const bounds = event.currentTarget.parentElement?.getBoundingClientRect();
                  if (!bounds) return;
                  setDrag({
                    id: el.id,
                    dx: (event.clientX - bounds.left) / SCALE - el.x,
                    dy: (event.clientY - bounds.top) / SCALE - el.y,
                  });
                }}
                className={`absolute overflow-hidden ${selected === el.id ? "ring-2 ring-primary" : ""}`}
                style={{
                  left: el.x * SCALE,
                  top: el.y * SCALE,
                  width: el.width * SCALE,
                  height: el.height * SCALE,
                  background: el.type === "rect" ? el.fill : "transparent",
                  color: el.color,
                  fontSize: (el.fontSize || 48) * SCALE,
                  backgroundImage: el.type === "image" && el.src ? `url(${el.src})` : undefined,
                  backgroundSize: "cover",
                }}
              >
                {el.type === "text" ? el.text : null}
              </div>
            ))}
          </div>
        </section>
        <aside className="w-72 space-y-3 overflow-y-auto border-l bg-white p-4 text-sm dark:bg-surface-dark">
          <label className="block">
            Background
            <input
              type="color"
              className="ml-2"
              value={data.background?.color || "#111827"}
              onChange={(e) => setData({ ...data, background: { color: e.target.value } })}
            />
          </label>
          {current ? (
            <>
              {current.type === "text" ? (
                <>
                  <textarea
                    className="w-full rounded-xl border p-2"
                    value={current.text}
                    onChange={(e) => update(current.id, { text: e.target.value })}
                  />
                  <label>
                    Size
                    <input
                      type="number"
                      className="ml-2 w-20 rounded border px-1"
                      value={current.fontSize}
                      onChange={(e) => update(current.id, { fontSize: Number(e.target.value) })}
                    />
                  </label>
                </>
              ) : null}
              {current.type === "rect" ? (
                <label>
                  Fill
                  <input type="color" className="ml-2" value={current.fill} onChange={(e) => update(current.id, { fill: e.target.value })} />
                </label>
              ) : null}
              <button
                type="button"
                className="text-red-600"
                onClick={() => {
                  setData({ ...data, elements: elements.filter((el) => el.id !== current.id) });
                  setSelected(null);
                }}
              >
                Delete
              </button>
            </>
          ) : (
            <p className="text-gray-500">Select an element to edit it.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
