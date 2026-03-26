"use client";

import { useState, useEffect, useSyncExternalStore } from "react";
import flourite from "flourite";
import Editor from "@monaco-editor/react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Loader2, ShieldCheck, ShieldAlert, Code2 } from "lucide-react";
import { ModeToggle } from "./mode-toggle";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const EDITOR_SKELETON_WIDTHS = [72, 88, 65, 91, 78, 55, 84, 70, 95, 63, 80, 68];
const MONACO_SKELETON_WIDTHS = [75, 90, 60, 85, 70, 95, 65, 80, 55, 88, 72, 93, 67, 78];

export function EditorClient() {
  const { resolvedTheme } = useTheme();

  const defaultTemplate = `// Hybrid Secret Scanner - Default Example
// This simulator enables you to visualize our ML-powered detection engine.

// Example 1: The engine should recognize this as a HIGH PRIORITY threat
const STRIPE_SECRET = "sk_live_51abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890";
const AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE";

// Example 2: The engine should classify this as a SAFE placeholder (low entropy)
const LOCAL_TEST_DB_PASSWORD = "test_password_12345";

export function App() {
  return <h1>Connected securely!</h1>;
}
`;

  const [code, setCode] = useState<string>(defaultTemplate);
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState<{
    status: "clean" | "threat";
    message: string;
  } | null>(null);
  const [direction, setDirection] = useState<"horizontal" | "vertical">(
    "horizontal",
  );

  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );

  useEffect(() => {
    const handleResize = () => {
      setDirection(window.innerWidth < 768 ? "vertical" : "horizontal");
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const detectLanguage = (code: string) => {
    try {
      const res = flourite(code);
      const lang = res.language;

      if (!lang || lang === "Unknown") {
        return { id: "javascript", label: "JavaScript" };
      }

      let id = lang.toLowerCase();
      if (id === "c++") id = "cpp";
      if (id === "c#") id = "csharp";

      let label = lang;
      if (label === "Javascript") label = "JavaScript";
      if (label === "Typescript") label = "TypeScript";

      return { id, label };
    } catch {
      return { id: "javascript", label: "JavaScript" };
    }
  };

  const currentLang = detectLanguage(code);

  const handleScan = () => {
    setIsScanning(true);
    setScanResult(null);

    setTimeout(() => {
      setIsScanning(false);
      if (code.includes("sk-")) {
        setScanResult({
          status: "threat",
          message: "Potential secret detected: Exposed API Key found.",
        });
      } else {
        setScanResult({
          status: "clean",
          message: "No secrets detected. Code looks clean.",
        });
      }
    }, 1500);
  };

  if (!mounted) {
    return (
      <div className="flex flex-col h-dvh w-full">
        {/* Header skeleton */}
        <div className="border-b p-4 flex items-center justify-between bg-card">
          <div className="flex flex-col gap-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
          <div className="flex items-center gap-4">
            <Skeleton className="h-9 w-9 rounded-md" />
            <Skeleton className="h-9 w-32 rounded-md" />
          </div>
        </div>
        {/* Editor + panel skeleton */}
        <div className="flex-1 flex flex-col md:flex-row">
          <div className="flex-1 p-4 flex flex-col gap-3">
            {EDITOR_SKELETON_WIDTHS.map((width, i) => (
              <Skeleton key={i} className="h-4" style={{ width: `${width}%` }} />
            ))}
          </div>
          <div className="w-full md:w-80 border-t md:border-t-0 md:border-l p-6 flex flex-col gap-4 bg-muted/20 h-40 md:h-auto">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-20 w-full rounded-xl" />
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-dvh w-full">
      <div className="border-b p-4 flex items-center justify-between bg-card">
        <div>
          <h1 className="text-xl font-bold">Secret Scanner Editor</h1>
          <p className="text-sm text-muted-foreground">
            Scan your code snippet for hardcoded secrets
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Tooltip>
            <TooltipTrigger render={<div className="inline-flex" />}>
              <ModeToggle />
            </TooltipTrigger>
            <TooltipContent>
              <p>Toggle Theme</p>
            </TooltipContent>
          </Tooltip>

          <Button
            onClick={handleScan}
            disabled={isScanning}
            className="min-w-32"
          >
            {isScanning ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Scanning...
              </>
            ) : (
              "Scan Code"
            )}
          </Button>
        </div>
      </div>

      <ResizablePanelGroup
        direction={direction}
        className="flex-1 w-full items-stretch"
      >
        <ResizablePanel
          defaultSize={direction === "vertical" ? 60 : 70}
          minSize={30}
          className="relative flex flex-col h-full bg-background"
        >
          <Editor
            height="100%"
            language={currentLang.id}
            theme={resolvedTheme === "light" ? "light" : "vs-dark"}
            value={code}
            onChange={(val) => setCode(val || "")}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              fontFamily: '"JetBrains Mono", "Fira Code", monospace',
              padding: { top: 20 },
              scrollBeyondLastLine: false,
              smoothScrolling: true,
              wordWrap: "on",
            }}
            loading={
              <div className="flex flex-col gap-3 p-6 w-full">
                {MONACO_SKELETON_WIDTHS.map((width, i) => (
                <Skeleton key={i} className="h-4" style={{ width: `${width}%` }} />
                ))}
              </div>
            }
          />
          <div className="absolute bottom-4 right-6 bg-background/80 backdrop-blur border text-muted-foreground text-xs px-3 py-1.5 rounded-md flex items-center gap-2 shadow-sm z-10 pointer-events-none">
            <Code2 className="h-4 w-4" />
            <span className="font-medium">{currentLang.label}</span>
          </div>
        </ResizablePanel>

        <ResizableHandle withHandle />

        <ResizablePanel
          defaultSize={direction === "vertical" ? 40 : 30}
          minSize={20}
          className={cn(
            "flex flex-col bg-muted/20",
            direction === "horizontal" ? "border-l" : "border-t",
          )}
        >
          <div className="p-6 h-full overflow-y-auto flex flex-col">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-6">
              Scan Results
            </h2>

            {isScanning && (
              <div className="flex flex-col gap-4">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-20 w-full rounded-xl" />
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-36" />
              </div>
            )}

            {!isScanning && scanResult && (
              <div
                className={`p-4 rounded-xl border flex gap-3 ${
                  scanResult.status === "clean"
                    ? "bg-green-500/10 border-green-500/20 text-green-700 dark:text-green-400"
                    : "bg-destructive/10 border-destructive/20 text-destructive"
                }`}
              >
                {scanResult.status === "clean" ? (
                  <ShieldCheck className="h-5 w-5 shrink-0 mt-0.5" />
                ) : (
                  <ShieldAlert className="h-5 w-5 shrink-0 mt-0.5" />
                )}
                <div className="flex flex-col gap-1">
                  <span className="font-semibold">
                    {scanResult.status === "clean" ? "Passed" : "Failed"}
                  </span>
                  <span className="text-sm opacity-90">
                    {scanResult.message}
                  </span>
                </div>
              </div>
            )}

            {!isScanning && !scanResult && (
              <div className="flex flex-col items-center justify-center py-12 text-center opacity-50">
                <ShieldCheck className="h-12 w-12 mb-4" />
                <p className="text-sm">
                  Click &quot;Scan Code&quot; to view results here.
                </p>
              </div>
            )}
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
