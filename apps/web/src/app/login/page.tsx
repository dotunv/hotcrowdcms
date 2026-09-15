"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: () => api.login(login, password),
    onSuccess: () => router.replace("/"),
  });

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background-light dark:bg-background-dark">
      <form
        className="w-full max-w-md bg-white dark:bg-surface-dark rounded-2xl p-8 border border-border-light dark:border-border-dark space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <h1 className="text-3xl font-bold text-center">Welcome back</h1>
        <p className="text-sm text-gray-500 text-center">Sign in to manage screens and playlists.</p>
        {mutation.isError ? <p className="text-sm text-red-600">{(mutation.error as Error).message}</p> : null}
        <label className="block text-sm font-medium">
          Username or email
          <input
            className="mt-1 w-full px-3 py-2.5 rounded-xl border bg-gray-50 dark:bg-gray-800"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            required
          />
        </label>
        <label className="block text-sm font-medium">
          Password
          <input
            type="password"
            className="mt-1 w-full px-3 py-2.5 rounded-xl border bg-gray-50 dark:bg-gray-800"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        <button type="submit" disabled={mutation.isPending} className="w-full py-3 bg-primary text-white font-bold rounded-xl disabled:opacity-50">
          {mutation.isPending ? "Signing in…" : "Sign in"}
        </button>
        <p className="text-sm text-center">
          <Link href="/forgot" className="text-primary font-semibold">
            Forgot password?
          </Link>
        </p>
        <p className="text-sm text-center text-gray-500">
          No account?{" "}
          <Link href="/register" className="text-primary font-semibold">
            Sign up
          </Link>
        </p>
      </form>
    </div>
  );
}
