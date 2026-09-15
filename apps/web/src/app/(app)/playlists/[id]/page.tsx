"use client";

import { use } from "react";
import { PlaylistBuilder } from "@/components/playlist-builder";

export default function PlaylistEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <PlaylistBuilder playlistId={id} />;
}
