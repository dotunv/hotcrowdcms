"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function StorePage() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["store"], queryFn: api.store });
  const [businessName, setBusinessName] = useState("");
  const [timezone, setTimezone] = useState("");
  const [description, setDescription] = useState("");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (data && !hydrated) {
      setBusinessName(data.business_name);
      setTimezone(data.timezone);
      setDescription(data.description);
      setHydrated(true);
    }
  }, [data, hydrated]);

  const save = useMutation({
    mutationFn: () =>
      api.patchStore({
        business_name: businessName,
        timezone,
        description,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["store"] });
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <div className="mx-auto max-w-lg p-8">
      <h1 className="text-2xl font-bold">Store</h1>
      <form onSubmit={onSubmit} className="mt-6 space-y-4 rounded-2xl border border-border-light bg-white p-6 dark:border-border-dark dark:bg-surface-dark">
        <label className="block text-sm font-medium">
          Name
          <input
            className="mt-1 w-full rounded-xl border border-border-light px-3 py-2 dark:border-border-dark dark:bg-gray-900"
            value={businessName}
            onChange={(e) => setBusinessName(e.target.value)}
          />
        </label>
        <label className="block text-sm font-medium">
          Timezone
          <input
            className="mt-1 w-full rounded-xl border border-border-light px-3 py-2 dark:border-border-dark dark:bg-gray-900"
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
          />
        </label>
        <label className="block text-sm font-medium">
          Description
          <textarea
            className="mt-1 w-full rounded-xl border border-border-light px-3 py-2 dark:border-border-dark dark:bg-gray-900"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
          />
        </label>
        {save.isSuccess ? <p className="text-sm text-primary">Store saved.</p> : null}
        {save.isError ? <p className="text-sm text-red-600">{(save.error as Error).message}</p> : null}
        <button className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white" type="submit">
          Save
        </button>
      </form>
    </div>
  );
}
