"use client";

import React, { useEffect, useId, useState } from "react";
import mermaid from "mermaid";
import { Maximize2, ZoomIn, ZoomOut, RotateCcw, X } from "lucide-react";

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
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [zoom, setZoom] = useState(1);

  // Close modal on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsModalOpen(false);
      }
    };
    if (isModalOpen) {
      window.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
      setZoom(1);
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "unset";
    };
  }, [isModalOpen]);

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
        }
      }

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
    <>
      {/* Clickable Diagram Card with Zoom Indicator */}
      <div className="relative group my-4">
        <div
          onClick={() => setIsModalOpen(true)}
          title="Click to enlarge diagram"
          className="cursor-zoom-in p-4 bg-slate-950/70 hover:bg-slate-950/90 border border-slate-800 hover:border-indigo-500/50 rounded-2xl overflow-x-auto flex justify-center shadow-lg shadow-black/40 max-w-full transition duration-150 [&_svg]:max-w-full [&_svg]:h-auto"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
        {/* Hover Action Badge */}
        <button
          onClick={() => setIsModalOpen(true)}
          className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-150 flex items-center gap-1 px-2.5 py-1 bg-indigo-600/90 hover:bg-indigo-600 text-white rounded-lg text-[11px] font-medium shadow-md backdrop-blur"
        >
          <Maximize2 className="w-3.5 h-3.5" />
          <span>Enlarge</span>
        </button>
      </div>

      {/* Full-Screen Lightbox / Zoom Modal */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex flex-col items-center justify-center p-4 md:p-8 animate-in fade-in duration-200"
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsModalOpen(false);
          }}
        >
          {/* Floating Controls Header */}
          <div className="w-full max-w-5xl flex items-center justify-between pb-4">
            <div className="flex items-center gap-2 text-slate-300 text-xs font-mono">
              <span className="px-2.5 py-1 bg-slate-800/90 border border-slate-700 rounded-lg">
                Zoom: {Math.round(zoom * 100)}%
              </span>
              <span className="text-slate-500 text-[11px] hidden sm:inline">
                (Press Esc or click outside to close)
              </span>
            </div>

            {/* Toolbar */}
            <div className="flex items-center gap-2 bg-slate-900/90 border border-slate-700/80 p-1 rounded-xl shadow-xl backdrop-blur">
              <button
                onClick={() => setZoom((z) => Math.min(z + 0.25, 3))}
                title="Zoom In"
                className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-300 hover:text-white transition"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                onClick={() => setZoom((z) => Math.max(z - 0.25, 0.5))}
                title="Zoom Out"
                className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-300 hover:text-white transition"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <button
                onClick={() => setZoom(1)}
                title="Reset Zoom"
                className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-300 hover:text-white transition"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
              <div className="w-[1px] h-4 bg-slate-700 mx-1" />
              <button
                onClick={() => setIsModalOpen(false)}
                title="Close"
                className="p-1.5 hover:bg-red-500/20 text-slate-300 hover:text-red-400 rounded-lg transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Modal SVG Canvas */}
          <div
            className="flex-1 w-full max-w-5xl bg-slate-950/90 border border-slate-800 rounded-2xl overflow-auto p-6 flex items-center justify-center shadow-2xl"
            onClick={(e) => {
              if (e.target === e.currentTarget) setIsModalOpen(false);
            }}
          >
            <div
              style={{
                transform: `scale(${zoom})`,
                transformOrigin: "center center",
                transition: "transform 0.15s ease-out",
              }}
              className="flex items-center justify-center max-w-none [&_svg]:max-w-none [&_svg]:h-auto"
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          </div>
        </div>
      )}
    </>
  );
}
