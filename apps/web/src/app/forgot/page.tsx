"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";

export default function ForgotPage() {
  const [email, setEmail] = useState("");
  const mutation = useMutation({
    mutationFn: () => api.forgotPassword(email),
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
        <h1 className="text-center text-3xl font-bold">Reset password</h1>
        <p className="text-center text-sm text-gray-500">We will email a reset link if that account exists.</p>
        {mutation.isSuccess ? (
          <div className="space-y-2 text-sm text-primary">
            <p>If that email is on an account, the reset link is on its way.</p>
            {mutation.data.reset_url ? (
              <p className="break-all text-gray-600 dark:text-gray-300">
                Local debug link:{" "}
                <Link href={mutation.data.reset_url} className="font-semibold underline">
                  set a new password
                </Link>
              </p>
            ) : null}
          </div>
        ) : null}
        <input
          type="email"
          required
          className="w-full rounded-xl border px-3 py-2.5 dark:bg-gray-800"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button disabled={mutation.isPending} className="w-full rounded-xl bg-primary py-3 font-bold text-white disabled:opacity-50">
          {mutation.isPending ? "Sending…" : "Send reset link"}
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
