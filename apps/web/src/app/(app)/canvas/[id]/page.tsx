"use client";

import { use } from "react";
import { CanvasEditor } from "@/components/canvas-editor";

export default function CanvasEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <CanvasEditor layoutId={id} />;
}
