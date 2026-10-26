"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast";
import { Page, ui } from "@/components/ui";

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
    <Page
      eyebrow="Plan"
      title="Billing"
      narrow
      subtitle="Starter is free. Pro unlocks more stores, screens, and Instagram sync."
    >
      <div className="grid gap-6 md:grid-cols-2">
        {(data?.plans ?? []).map((plan) => {
          const current = data?.plan === plan.id;
          const pro = plan.id === "pro";
          return (
            <div
              key={plan.id}
              className={`flex flex-col rounded-[20px] border-[3px] p-7 ${
                pro
                  ? "border-[#0E1A14] bg-[#B2F2BB] text-[#0E1A14] dark:border-[#F2F5F0]"
                  : "border-[#E8EAE6] dark:border-[#2A322C]"
              }`}
            >
              <p className={`text-xs font-semibold uppercase tracking-[0.14em] ${pro ? "text-[#045E33]" : ui.muted}`}>{plan.label}</p>
              <p className="mt-3 text-[56px] font-extrabold leading-[56px] tracking-[-0.05em]">{pro ? "Pro" : "Free"}</p>
              <ul className={`mt-6 flex-1 space-y-2 text-[15px] font-semibold ${pro ? "text-[#0E1A14]" : ui.muted}`}>
                <li>
                  {plan.stores} store{plan.stores === 1 ? "" : "s"}
                </li>
                <li>{plan.screens} screens per store</li>
                <li>{pro ? "Instagram Graph sync" : "Manual Instagram import"}</li>
              </ul>
              {pro && !current ? (
                <button
                  type="button"
                  className="mt-8 w-full rounded-xl bg-[#0E1A14] py-3 text-sm font-bold text-white dark:bg-[#0E1A14]"
                  onClick={() => checkout.mutate()}
                >
                  {data?.stripe_configured ? "Continue to Stripe" : "Upgrade in this environment"}
                </button>
              ) : null}
              {current ? (
                <p className={`mt-8 text-xs font-bold uppercase tracking-[0.14em] ${pro ? "text-[#045E33]" : "text-primary dark:text-[#B2F2BB]"}`}>
                  Current plan
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
      {checkout.isError ? <p className={ui.error}>{(checkout.error as Error).message}</p> : null}
    </Page>
  );
}
