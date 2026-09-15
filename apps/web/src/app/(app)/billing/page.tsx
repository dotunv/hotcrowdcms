"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast";

export default function BillingPage() {
  const toast = useToast();
  const client = useQueryClient();
  const billing = useQuery({ queryKey: ["billing"], queryFn: api.billing });
  const checkout = useMutation({
    mutationFn: api.startCheckout,
    onSuccess: (data) => {
      if (data.url) {
        window.location.href = data.url;
        return;
      }
      void client.invalidateQueries();
      toast("Pro is on for this account.");
    },
  });

  const data = billing.data;
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold">Billing</h1>
        <p className="mt-1 text-sm text-gray-500">Starter is free. Pro unlocks more stores, screens, and Instagram sync.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {(data?.plans ?? []).map((plan) => (
          <div key={plan.id} className={`rounded-2xl border p-6 ${data?.plan === plan.id ? "border-primary" : ""}`}>
            <p className="text-sm text-gray-500">{plan.label}</p>
            <p className="mt-2 text-3xl font-bold">{plan.id === "starter" ? "Free" : "Pro"}</p>
            <ul className="mt-4 space-y-1 text-sm text-gray-500">
              <li>{plan.stores} store{plan.stores === 1 ? "" : "s"}</li>
              <li>{plan.screens} screens per store</li>
              <li>{plan.id === "pro" ? "Instagram Graph sync" : "Manual Instagram import"}</li>
            </ul>
            {plan.id === "pro" && data?.plan !== "pro" ? (
              <button
                type="button"
                className="mt-6 w-full rounded-xl bg-primary py-2 text-sm font-bold text-white"
                onClick={() => checkout.mutate()}
              >
                {data?.stripe_configured ? "Continue to Stripe" : "Upgrade in this environment"}
              </button>
            ) : null}
            {data?.plan === plan.id ? <p className="mt-6 text-sm font-semibold text-primary">Current plan</p> : null}
          </div>
        ))}
      </div>
      {checkout.isError ? <p className="text-sm text-red-600">{(checkout.error as Error).message}</p> : null}
    </div>
  );
}
