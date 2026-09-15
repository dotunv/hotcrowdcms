export default function HelpPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold">How HotCrowd works</h1>
        <p className="mt-1 text-sm text-gray-500">Same loop as before: pair, upload, playlist, assign, play.</p>
      </div>
      <ol className="list-decimal space-y-3 pl-5 text-sm text-gray-600 dark:text-gray-300">
        <li>Open the player and connect it with the 8-character code on Screens.</li>
        <li>Drop images and videos into the library.</li>
        <li>Build a playlist, drag to reorder, then publish. Drafts do not play on the TV.</li>
        <li>Assign that playlist to the screen. The player heartbeats and fetches url, type, duration, and position. Off-schedule or empty loops use the store fallback.</li>
      </ol>
      <div className="rounded-2xl border bg-white p-5 text-sm dark:border-border-dark dark:bg-surface-dark">
        <p className="font-semibold">Stores, canvas, billing, Instagram</p>
        <p className="mt-1 text-gray-500">
          Switch locations in the sidebar. Canvas layouts publish into the library as images the player can loop. Starter includes one store and two screens; Pro is billed through Stripe when configured. Instagram imports a media URL on any plan; Graph sync is Pro and uses an official access token, not a password.
        </p>
      </div>
    </div>
  );
}
