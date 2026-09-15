"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: () => api.register(username, email, password),
    onSuccess: () => router.replace("/"),
  });

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background-light dark:bg-background-dark">
      <form
        className="w-full max-w-md bg-white dark:bg-surface-dark rounded-2xl p-8 border space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <h1 className="text-3xl font-bold text-center">Create account</h1>
        {mutation.isError ? <p className="text-sm text-red-600">{(mutation.error as Error).message}</p> : null}
        <input className="w-full px-3 py-2.5 rounded-xl border bg-gray-50 dark:bg-gray-800" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        <input type="email" className="w-full px-3 py-2.5 rounded-xl border bg-gray-50 dark:bg-gray-800" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input type="password" className="w-full px-3 py-2.5 rounded-xl border bg-gray-50 dark:bg-gray-800" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
        <button type="submit" disabled={mutation.isPending} className="w-full py-3 bg-primary text-white font-bold rounded-xl">
          {mutation.isPending ? "Creating…" : "Create account"}
        </button>
        <p className="text-sm text-center">
          Already have an account?{" "}
          <Link href="/login" className="text-primary font-semibold">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
