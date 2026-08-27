"use client";

import React, { useEffect, useId, useState } from "react";
import mermaid from "mermaid";

let mermaidInitialized = false;

function initMermaid() {
  if (typeof window !== "undefined" && !mermaidInitialized) {
    mermaid.initialize({
      startOnLoad: false,
      suppressErrorRendering: true,
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

/**
 * Auto-quotes unquoted node labels with parentheses, slashes, or special symbols
 * e.g., NodeA[Text (with details) / extra] -> NodeA["Text (with details) / extra"]
 */
function sanitizeMermaid(chart: string): string {
  return chart
    .split("\n")
    .map((line) => {
      // If line has node definition with [ ... ] and unquoted special chars like ( ) / & :
      return line.replace(
        /(\b\w+)\s*\[([^"\]\n]*[()\/&:#,][^"\]\n]*)\]/g,
        '$1["$2"]'
      );
    })
    .join("\n");
}

function stripStyles(chart: string): string {
  return chart
    .split("\n")
    .filter((line) => !line.trim().startsWith("style ") && !line.trim().startsWith("classDef "))
    .join("\n");
}

function cleanStrayDOMElements() {
  if (typeof document !== "undefined") {
    // Remove any stray error elements injected by mermaid on document.body
    const strayErrors = document.querySelectorAll(
      'div[id^="dmermaid"], div[id^="mermaid-"], svg[id^="dmermaid"]'
    );
    strayErrors.forEach((el) => {
      if (el.parentElement === document.body) {
        el.remove();
      }
    });
  }
}

interface MermaidProps {
  chart: string;
}

export function Mermaid({ chart }: MermaidProps) {
  const rawId = useId();
  const id = `mm-${rawId.replace(/[^a-zA-Z0-9]/g, "")}`;
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    initMermaid();

    async function renderChart() {
      if (!chart || !chart.trim()) return;

      const raw = chart.trim();
      const sanitized = sanitizeMermaid(raw);
      const candidates = [
        sanitized,
        stripStyles(sanitized),
        raw,
        stripStyles(raw),
      ];

      for (let i = 0; i < candidates.length; i++) {
        const codeToTest = candidates[i];
        try {
          // Test parse first (suppressErrorRendering prevents DOM error bomb injection)
          const isValid = await mermaid.parse(codeToTest, { suppressErrors: true });
          if (!isValid) continue;

          const renderId = `${id}-${i}`;
          const { svg: renderedSvg } = await mermaid.render(renderId, codeToTest);
          if (isMounted) {
            setSvg(renderedSvg);
            setError(null);
            cleanStrayDOMElements();
            return;
          }
        } catch {
          cleanStrayDOMElements();
          // continue to next candidate
        }
      }

      // If all candidates failed parse/render, gracefully fallback without DOM bombs
      if (isMounted) {
        cleanStrayDOMElements();
        setError("Diagram syntax could not be rendered visually");
      }
    }

    renderChart();

    return () => {
      isMounted = false;
      cleanStrayDOMElements();
    };
  }, [chart, id]);

  if (error) {
    return (
      <div className="my-3 p-3 bg-slate-900/90 border border-slate-800 rounded-xl text-xs font-mono text-slate-300 max-w-full overflow-hidden">
        <div className="text-slate-400 font-semibold mb-1 text-[11px] flex items-center justify-between">
          <span>📊 Flowchart / Sequence (Raw Specification Text)</span>
        </div>
        <pre className="overflow-x-auto text-[11px] text-slate-400 font-mono leading-relaxed p-2 bg-black/40 rounded-lg">
          {chart}
        </pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="my-3 p-4 bg-slate-950/40 border border-slate-800/80 rounded-xl flex items-center justify-center text-xs text-slate-400 font-mono">
        <span className="animate-pulse">Rendering diagram...</span>
      </div>
    );
  }

  return (
    <div
      className="my-4 p-4 bg-slate-950/70 border border-slate-800/80 rounded-2xl overflow-x-auto flex justify-center shadow-lg shadow-black/40 max-w-full [&_svg]:max-w-full [&_svg]:h-auto"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
