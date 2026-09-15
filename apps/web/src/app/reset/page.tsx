"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api } from "@/lib/api";

function ResetForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") || "";
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: () => api.resetPassword(token, password),
    onSuccess: () => router.replace("/login"),
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-background-light p-6 dark:bg-background-dark">
      <form
        className="w-full max-w-md space-y-4 rounded-2xl border border-border-light bg-white p-8 dark:border-border-dark dark:bg-surface-dark"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <h1 className="text-center text-3xl font-bold">Choose a new password</h1>
        {!token ? <p className="text-sm text-red-600">This reset link is missing a token.</p> : null}
        {mutation.isError ? <p className="text-sm text-red-600">{(mutation.error as Error).message}</p> : null}
        <input
          type="password"
          required
          minLength={8}
          className="w-full rounded-xl border px-3 py-2.5 dark:bg-gray-800"
          placeholder="New password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button
          disabled={mutation.isPending || !token}
          className="w-full rounded-xl bg-primary py-3 font-bold text-white disabled:opacity-50"
        >
          {mutation.isPending ? "Saving…" : "Update password"}
        </button>
        <p className="text-center text-sm">
          <Link href="/login" className="font-semibold text-primary">
            Back to sign in
          </Link>
        </p>
      </form>
    </div>
  );
}

export default function ResetPage() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
