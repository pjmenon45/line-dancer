"use client";

import React, { useEffect, useId, useState } from "react";
import mermaid from "mermaid";

let mermaidInitialized = false;

function initMermaid() {
  if (typeof window !== "undefined" && !mermaidInitialized) {
    mermaid.initialize({
      startOnLoad: false,
      theme: "dark",
      securityLevel: "loose",
      fontFamily: "ui-sans-serif, system-ui, sans-serif",
      themeVariables: {
        darkMode: true,
        background: "#090d16",
        primaryColor: "#4f46e5",
        primaryTextColor: "#f8fafc",
        primaryBorderColor: "#6366f1",
        lineColor: "#94a3b8",
        secondaryColor: "#1e293b",
        tertiaryColor: "#0f172a",
        noteBkgColor: "#1e1b4b",
        noteTextColor: "#e0e7ff",
        noteBorderColor: "#4338ca",
        actorBkg: "#1e1b4b",
        actorTextColor: "#ffffff",
        actorBorder: "#6366f1",
        signalColor: "#cbd5e1",
        signalTextColor: "#ffffff",
      },
    });
    mermaidInitialized = true;
  }
}

function sanitizeMermaid(chart: string): string {
  return chart
    .split("\n")
    .map((line) => {
      // Auto-quote square bracket node labels that contain parentheses, slashes, or special characters:
      // e.g. Node[Text (detail) / extra] -> Node["Text (detail) / extra"]
      return line.replace(
        /(\b\w+)\s*\[([^"\]\n]*[()\/&:#,][^"\]\n]*)\]/g,
        '$1["$2"]'
      );
    })
    .join("\n");
}

function stripStyles(chart: string): string {
  // Strip style and class lines if they contain malformed CSS syntax
  return chart
    .split("\n")
    .filter((line) => !line.trim().startsWith("style ") && !line.trim().startsWith("classDef "))
    .join("\n");
}

interface MermaidProps {
  chart: string;
}

export function Mermaid({ chart }: MermaidProps) {
  const rawId = useId();
  const id = `mermaid-${rawId.replace(/:/g, "")}`;
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    initMermaid();

    async function renderChart() {
      if (!chart.trim()) return;

      const candidates = [
        sanitizeMermaid(chart.trim()),
        stripStyles(sanitizeMermaid(chart.trim())),
        chart.trim(),
      ];

      for (let i = 0; i < candidates.length; i++) {
        try {
          const candidateId = `${id}-${i}`;
          const { svg: renderedSvg } = await mermaid.render(candidateId, candidates[i]);
          if (isMounted) {
            setSvg(renderedSvg);
            setError(null);
            return;
          }
        } catch (err: any) {
          // If last candidate fails, report error
          if (i === candidates.length - 1 && isMounted) {
            console.warn("Mermaid render fallback failed:", err);
            setError(err?.message || "Syntax error in Mermaid diagram");
          }
        }
      }
    }

    renderChart();

    return () => {
      isMounted = false;
    };
  }, [chart, id]);

  if (error) {
    return (
      <div className="my-3 p-3 bg-slate-900/90 border border-amber-500/30 rounded-xl text-xs font-mono text-slate-300">
        <div className="text-amber-400 font-semibold mb-1 flex items-center gap-1.5">
          <span>⚠️ Diagram Syntax View (raw code)</span>
        </div>
        <pre className="overflow-x-auto text-[11px] text-slate-400">{chart}</pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="my-3 p-6 bg-slate-950/40 border border-slate-800 rounded-xl flex items-center justify-center text-xs text-slate-400 font-mono">
        <span className="animate-pulse">Rendering diagram...</span>
      </div>
    );
  }

  return (
    <div
      className="my-4 p-4 bg-slate-950/70 border border-slate-800/80 rounded-2xl overflow-x-auto flex justify-center shadow-lg shadow-black/40 [&_svg]:max-w-full [&_svg]:h-auto"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
