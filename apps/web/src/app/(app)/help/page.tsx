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
        <p className="font-semibold">Password reset</p>
        <p className="mt-1 text-gray-500">
          Use Forgot password on the sign-in page. In production that email needs SMTP. In local debug, the reset link is shown on the page and printed in the API console.
        </p>
      </div>
    </div>
  );
}
