import type { Metadata } from "next";
import { EditorClient } from "@/components/editor-client";

export const metadata: Metadata = {
  title: "Hybrid Secret Scanner",
  description:
    "Detect hardcoded API keys and secrets using an advanced machine learning model directly in our web editor.",
};

export default function Page() {
  return <EditorClient />;
}
