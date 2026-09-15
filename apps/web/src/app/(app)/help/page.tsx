export default function HelpPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-4 p-8">
      <h1 className="text-2xl font-bold">How HotCrowd works</h1>
      <ol className="list-decimal space-y-2 pl-5 text-sm text-gray-600 dark:text-gray-300">
        <li>Pair a player with the 8-character code shown on the TV.</li>
        <li>Upload images and videos in the library.</li>
        <li>Build a playlist and assign it to the screen.</li>
        <li>The player heartbeats and fetches url, type, duration, and position until you change the loop.</li>
      </ol>
    </div>
  );
}
