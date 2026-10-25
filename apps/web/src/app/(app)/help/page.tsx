import { Page } from "@/components/ui";

const STEPS = [
  "Open the player and connect it with the 8-character code on Screens.",
  "Drop images and videos into the library.",
  "Build a playlist, drag to reorder, then publish. Drafts do not play on the TV.",
  "Assign that playlist to the screen. The player heartbeats and fetches url, type, duration, and position. Off-schedule or empty loops use the store fallback.",
];

export default function HelpPage() {
  return (
    <Page
      eyebrow="Guide"
      title="How HotCrowd works"
      narrow
      subtitle="Same loop as before: pair, upload, playlist, assign, play."
    >
      <ol>
        {STEPS.map((step, index) => (
          <li
            key={step}
            className={`flex items-start gap-6 py-6 ${
              index === 0 ? "border-t-2 border-[#0E1A14] dark:border-[#F2F5F0]" : "border-t border-[#E8EAE6] dark:border-[#2A322C]"
            } ${index === STEPS.length - 1 ? "border-b border-b-[#E8EAE6] dark:border-b-[#2A322C]" : ""}`}
          >
            <span className="w-12 shrink-0 text-[32px] font-extrabold tracking-[-0.04em] text-primary dark:text-[#B2F2BB]">
              {String(index + 1).padStart(2, "0")}
            </span>
            <p className="flex-1 pt-1.5 text-[15px] font-medium leading-[22px]">{step}</p>
          </li>
        ))}
      </ol>
      <div className="rounded-2xl bg-[#B2F2BB] p-7 text-[#0E1A14]">
        <p className="text-xl font-extrabold tracking-[-0.02em]">Stores, canvas, billing, Instagram</p>
        <p className="mt-2 text-[15px] font-medium leading-[22px]">
          Switch locations in the sidebar. Canvas layouts publish into the library as images the player can loop. Starter includes one store and two screens; Pro is billed through Stripe when configured. Instagram imports a media URL on any plan; Graph sync is Pro and uses an official access token, not a password.
        </p>
      </div>
    </Page>
  );
}
