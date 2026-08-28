"use client";

import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Send,
  Bot,
  User,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Loader2,
  Copy,
  Check,
  Layers,
  FileText,
  Download,
  Play,
  CheckCircle2,
  ArrowRight,
  BookOpen,
  Cpu,
  Radio,
  FileCheck,
} from "lucide-react";
import { Mermaid } from "@/components/Mermaid";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "https://line-dancer.onrender.com";

interface Message {
  role: "user" | "assistant";
  content: string;
  evidence?: string;
  stage?: string;
}

const SAMPLE_QUESTIONS = [
  "Explain the 5G Service-Based Architecture (SBA) in TS 23.501 and TS 29.500 with a Mermaid diagram.",
  "What does TS 38.331 cover regarding RRC connection establishment? Include a sequence diagram and timer table.",
  "How does 5G Converged Charging work in TS 32.290 and TS 32.255 (CHF, Nchf interface)?",
  "Summarize 5G Primary Authentication (5G-AKA vs EAP-AKA') in TS 33.501 with a call flow diagram.",
];

const HLD_PRESETS = [
  {
    title: "Regenerative Satellite Payloads for NTN",
    description: "On-board gNB-DU or full gNB processing on LEO/GEO satellites, ISL inter-satellite links, and Doppler/delay compensation across TS 38.300, TS 38.401, TS 23.501, and TS 38.331.",
    releases: ["Rel-17", "Rel-18", "Rel-19"],
  },
  {
    title: "On-Demand Network Energy Savings (NES)",
    description: "Dynamic cell/carrier switch-off, on-demand SSB/SI broadcast, AI/ML-driven traffic adaptation, and OAM energy coordination across TS 38.401, TS 28.104, and TS 38.300.",
    releases: ["Rel-18", "Rel-19"],
  },
  {
    title: "Ambient IoT & Zero-Energy Devices",
    description: "Backscatter communications, energy-harvesting IoT nodes, simplified PHY/MAC procedures, and Core network reachability across TS 38.850, TS 23.501, and TS 38.331.",
    releases: ["Rel-19"],
  },
  {
    title: "URLLC Industrial Ethernet & Redundancy",
    description: "Time-Sensitive Networking (TSN), dual connectivity redundant user planes, Ethernet header compression, and PDCP duplication across TS 23.501, TS 38.300, and TS 38.323.",
    releases: ["Rel-16", "Rel-17", "Rel-18"],
  },
];

const ALL_RELEASES = ["Rel-15", "Rel-16", "Rel-17", "Rel-18", "Rel-19"];

function CodeBlock({ className, children }: { className?: string; children: React.ReactNode }) {
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className || "");
  const language = match ? match[1].toLowerCase() : "";
  const codeString = String(children || "").replace(/\n$/, "");

  const isMermaid =
    language === "mermaid" ||
    /^\s*(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|gitGraph|journey|mindmap)\b/i.test(
      codeString.trim()
    );

  if (isMermaid) {
    return <Mermaid chart={codeString} />;
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(codeString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-slate-700/70 bg-slate-950/80 shadow-md max-w-full">
      <div className="px-3.5 py-1.5 bg-slate-900 border-b border-slate-800 text-[11px] text-slate-400 font-mono flex justify-between items-center">
        <span className="font-semibold text-slate-300 uppercase tracking-wider">{language || "code"}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-indigo-300 transition"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <pre className="p-3.5 text-xs overflow-x-auto font-mono text-slate-200 leading-relaxed max-w-full">
        <code>{codeString}</code>
      </pre>
    </div>
  );
}

export default function Home() {
  // Navigation Mode: "research" (Chat Q&A) or "hld" (New Feature HLD Agent)
  const [activeTab, setActiveTab] = useState<"research" | "hld">("research");

  // Research Mode State
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [openEvidence, setOpenEvidence] = useState<{ [key: number]: boolean }>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // HLD Agent State
  const [hldFeature, setHldFeature] = useState("");
  const [hldDescription, setHldDescription] = useState("");
  const [hldReleases, setHldReleases] = useState<string[]>(["Rel-17", "Rel-18", "Rel-19"]);
  const [hldLoading, setHldLoading] = useState(false);
  const [hldStatus, setHldStatus] = useState<string | null>(null);
  const [hldCurrentStage, setHldCurrentStage] = useState<number>(0); // 0: idle, 1: scanning, 2: extracting, 3: architecting, 4: done
  const [impactMap, setImpactMap] = useState<string>("");
  const [parametersLedger, setParametersLedger] = useState<string>("");
  const [hldDocument, setHldDocument] = useState<string>("");
  const [openImpact, setOpenImpact] = useState(false);
  const [openLedger, setOpenLedger] = useState(false);
  const [copiedHld, setCopiedHld] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, status]);

  const toggleEvidence = (idx: number) => {
    setOpenEvidence((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const toggleRelease = (rel: string) => {
    setHldReleases((prev) =>
      prev.includes(rel) ? prev.filter((r) => r !== rel) : [...prev, rel]
    );
  };

  const applyPreset = (preset: typeof HLD_PRESETS[0]) => {
    setHldFeature(preset.title);
    setHldDescription(preset.description);
    setHldReleases(preset.releases);
  };

  // --- Research Chat Submit ---
  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || input;
    if (!textToSend.trim() || loading) return;

    const userMessage: Message = { role: "user", content: textToSend };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setStatus("Initiating 3GPP Researcher Agent…");

    try {
      const response = await fetch(`${BACKEND_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: textToSend,
          include_evidence: true,
          series: null,
          releases: ["Rel-15", "Rel-16", "Rel-17", "Rel-18", "Rel-19"],
        }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantMsg: Message = { role: "assistant", content: "", evidence: "" };
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          const eventMatch = block.match(/event:\s*(\w+)/);
          const dataMatch = block.match(/data:\s*(.+)/);
          if (!eventMatch || !dataMatch) continue;

          const event = eventMatch[1];
          const data = JSON.parse(dataMatch[1]);

          if (event === "status") {
            setStatus(data.message);
          } else if (event === "evidence") {
            assistantMsg.evidence = data.text;
          } else if (event === "answer") {
            assistantMsg.content = data.text;
            setMessages((prev) => {
              const updated = [...prev];
              if (updated[updated.length - 1]?.role === "assistant") {
                updated[updated.length - 1] = assistantMsg;
              } else {
                updated.push(assistantMsg);
              }
              return updated;
            });
          } else if (event === "error") {
            assistantMsg.content = `❌ **Backend Error:** ${data.detail || "An unexpected error occurred during research."}`;
            setMessages((prev) => {
              const updated = [...prev];
              if (updated[updated.length - 1]?.role === "assistant") {
                updated[updated.length - 1] = assistantMsg;
              } else {
                updated.push(assistantMsg);
              }
              return updated;
            });
          }
        }
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `❌ Error connecting to backend: ${err.message}` },
      ]);
    } finally {
      setLoading(false);
      setStatus(null);
    }
  };

  // --- HLD Generation Submit ---
  const handleGenerateHLD = async () => {
    if (!hldFeature.trim() || hldLoading) return;

    setHldLoading(true);
    setHldStatus("Starting 3-Stage New Feature HLD Pipeline…");
    setHldCurrentStage(1);
    setImpactMap("");
    setParametersLedger("");
    setHldDocument("");

    try {
      const response = await fetch(`${BACKEND_URL}/hld/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feature_name: hldFeature,
          feature_description: hldDescription,
          target_releases: hldReleases.length > 0 ? hldReleases : ALL_RELEASES,
          include_intermediates: true,
        }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          const eventMatch = block.match(/event:\s*(\w+)/);
          const dataMatch = block.match(/data:\s*(.+)/);
          if (!eventMatch || !dataMatch) continue;

          const event = eventMatch[1];
          const data = JSON.parse(dataMatch[1]);

          if (event === "status") {
            setHldStatus(data.message);
            if (data.stage === "scanner") setHldCurrentStage(1);
            if (data.stage === "extractor") setHldCurrentStage(2);
            if (data.stage === "architect") setHldCurrentStage(3);
          } else if (event === "impact_map") {
            setImpactMap(data.text);
          } else if (event === "parameters_ledger") {
            setParametersLedger(data.text);
          } else if (event === "hld_document") {
            setHldDocument(data.text);
            setHldCurrentStage(4);
          } else if (event === "done") {
            setHldCurrentStage(4);
          } else if (event === "error") {
            setHldDocument((prev) => (prev && prev.length > 50 ? prev : `❌ **HLD Generation Error:** ${data.detail || "An error occurred."}`));
            setHldCurrentStage(4);
          }
        }
      }
    } catch (err: any) {
      setHldDocument((prev) => (prev && prev.length > 50 ? prev : `❌ **Connection Error:** ${err.message}`));
      setHldCurrentStage(4);
    } finally {
      setHldLoading(false);
      setHldStatus(null);
    }
  };

  const copyHLD = () => {
    navigator.clipboard.writeText(hldDocument);
    setCopiedHld(true);
    setTimeout(() => setCopiedHld(false), 2000);
  };

  const downloadHLD = () => {
    const filename = `${hldFeature.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-HLD.md`;
    const blob = new Blob([hldDocument], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100 selection:bg-indigo-500 selection:text-white">
      {/* Main Top Header with Mode Tabs */}
      <header className="px-4 md:px-6 py-3 border-b border-slate-800/80 flex flex-col md:flex-row md:items-center justify-between gap-3 bg-slate-950/90 backdrop-blur sticky top-0 z-30">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-xl border border-indigo-500/30 shadow-inner">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-semibold text-base flex items-center gap-2">
              <span>3GPP Standards Studio</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                Rel-15 to Rel-19
              </span>
            </h1>
            <p className="text-[11px] text-slate-400">Core (TS 23/24/29), Charging (TS 32), Security (TS 33), LTE (TS 36), NR (TS 38)</p>
          </div>
        </div>

        {/* Dual Mode Switcher Tabs */}
        <div className="flex items-center gap-1.5 bg-slate-900/90 border border-slate-800 p-1 rounded-xl shadow-inner self-start md:self-auto">
          <button
            onClick={() => setActiveTab("research")}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === "research"
                ? "bg-indigo-600 text-white shadow-md shadow-indigo-950"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-850"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Standards Research & Q&A</span>
          </button>

          <button
            onClick={() => setActiveTab("hld")}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === "hld"
                ? "bg-indigo-600 text-white shadow-md shadow-indigo-950"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-850"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>New Feature HLD Agent</span>
            <span className="bg-emerald-500/20 text-emerald-300 text-[10px] px-1.5 py-0.2 rounded-full border border-emerald-500/30">
              3-Stage
            </span>
          </button>
        </div>
      </header>

      {/* ========================================================================= */}
      {/* MODE 1: STANDARDS RESEARCH & Q&A */}
      {/* ========================================================================= */}
      {activeTab === "research" && (
        <div className="flex-1 flex flex-col min-h-0">
          <main className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 max-w-4xl w-full mx-auto">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-6 py-8">
                <div className="p-4 bg-indigo-950/40 border border-indigo-500/30 rounded-2xl shadow-xl shadow-indigo-950/50">
                  <Sparkles className="w-8 h-8 text-indigo-400" />
                </div>
                <div className="max-w-md space-y-2">
                  <h2 className="text-xl font-bold">Query 3GPP Technical Specifications</h2>
                  <p className="text-sm text-slate-400">
                    The Researcher agent queries official 3GPP specifications across all series, and the Analyst agent synthesizes reports with comparison tables, sequence diagrams, and citations.
                  </p>
                </div>
                <div className="grid grid-cols-1 gap-2.5 w-full max-w-xl text-left">
                  {SAMPLE_QUESTIONS.map((q, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSend(q)}
                      className="p-3.5 text-xs bg-slate-900 hover:bg-slate-850 hover:border-indigo-500/50 border border-slate-800 rounded-xl transition text-slate-300 hover:text-white shadow-sm"
                    >
                      "{q}"
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m, idx) => (
                <div
                  key={idx}
                  className={`flex gap-3 ${m.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {m.role === "assistant" && (
                    <div className="w-8 h-8 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0 mt-1 shadow-sm">
                      <Bot className="w-4 h-4 text-indigo-400" />
                    </div>
                  )}
                  <div className={`flex-1 min-w-0 max-w-[90%] md:max-w-[85%] space-y-3 ${m.role === "user" ? "items-end" : "items-start"}`}>
                    <div
                      className={`p-4 md:p-5 rounded-2xl text-sm leading-relaxed max-w-full overflow-hidden ${
                        m.role === "user"
                          ? "bg-indigo-600 text-white rounded-br-none shadow-md shadow-indigo-950/40"
                          : "bg-slate-900/90 border border-slate-800 text-slate-200 rounded-bl-none shadow-lg shadow-black/20"
                      }`}
                    >
                      {m.role === "user" ? (
                        m.content
                      ) : (
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            table: ({ node, ...props }) => (
                              <div className="my-4 overflow-x-auto border border-slate-700/80 rounded-xl shadow-lg bg-slate-950/60 max-w-full">
                                <table className="w-full text-left border-collapse text-xs md:text-sm" {...props} />
                              </div>
                            ),
                            thead: ({ node, ...props }) => (
                              <thead className="bg-indigo-950/50 text-indigo-200 border-b border-slate-700 font-semibold" {...props} />
                            ),
                            th: ({ node, ...props }) => (
                              <th className="py-3 px-4 font-semibold text-slate-200 uppercase tracking-wider text-[11px] border-r border-slate-800/80 last:border-r-0" {...props} />
                            ),
                            tbody: ({ node, ...props }) => (
                              <tbody className="divide-y divide-slate-800/80" {...props} />
                            ),
                            tr: ({ node, ...props }) => (
                              <tr className="hover:bg-slate-850/60 transition-colors" {...props} />
                            ),
                            td: ({ node, ...props }) => (
                              <td className="py-2.5 px-4 text-slate-300 border-r border-slate-800/60 last:border-r-0 align-top leading-relaxed" {...props} />
                            ),
                            h1: ({ node, ...props }) => (
                              <h1 className="text-xl font-bold text-slate-100 mt-6 mb-3 border-b border-slate-800 pb-2" {...props} />
                            ),
                            h2: ({ node, ...props }) => (
                              <h2 className="text-lg font-bold text-indigo-300 mt-5 mb-2.5" {...props} />
                            ),
                            h3: ({ node, ...props }) => (
                              <h3 className="text-base font-semibold text-slate-200 mt-4 mb-2" {...props} />
                            ),
                            p: ({ node, ...props }) => (
                              <p className="mb-3 leading-relaxed text-slate-300 last:mb-0" {...props} />
                            ),
                            ul: ({ node, ...props }) => (
                              <ul className="list-disc list-inside space-y-1.5 my-2.5 text-slate-300" {...props} />
                            ),
                            ol: ({ node, ...props }) => (
                              <ol className="list-decimal list-inside space-y-1.5 my-2.5 text-slate-300" {...props} />
                            ),
                            li: ({ node, ...props }) => (
                              <li className="leading-relaxed text-slate-300" {...props} />
                            ),
                            blockquote: ({ node, ...props }) => (
                              <blockquote className="my-3 pl-4 border-l-2 border-indigo-500 text-slate-400 italic bg-indigo-950/20 py-2 rounded-r-lg" {...props} />
                            ),
                            code: ({ node, className, children, ...props }: any) => {
                              const codeString = String(children || "");
                              const hasLang = Boolean(className && /language-/.test(className));
                              const hasNewlines = codeString.includes("\n");

                              if (!hasLang && !hasNewlines) {
                                return (
                                  <code
                                    className="bg-slate-800/90 text-indigo-300 px-1.5 py-0.5 rounded text-[12px] font-mono border border-slate-700/60 break-all inline"
                                    {...props}
                                  >
                                    {children}
                                  </code>
                                );
                              }

                              return <CodeBlock className={className}>{children}</CodeBlock>;
                            },
                          }}
                        >
                          {m.content}
                        </ReactMarkdown>
                      )}
                    </div>

                    {/* Collapsible Evidence Pack */}
                    {m.evidence && (
                      <div className="border border-slate-800 rounded-xl bg-slate-950/60 overflow-hidden shadow-sm max-w-full">
                        <button
                          onClick={() => toggleEvidence(idx)}
                          className="w-full px-3.5 py-2.5 text-xs flex items-center justify-between text-slate-400 hover:text-slate-200 bg-slate-900/60 transition"
                        >
                          <span className="font-mono flex items-center gap-2">
                            <span>📑</span>
                            <span>Researcher Evidence Pack (3GPP Raw Excerpts)</span>
                          </span>
                          {openEvidence[idx] ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </button>
                        {openEvidence[idx] && (
                          <div className="p-3.5 text-xs font-mono text-slate-300 bg-black/50 border-t border-slate-800 max-h-72 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                            {m.evidence}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  {m.role === "user" && (
                    <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 mt-1">
                      <User className="w-4 h-4 text-slate-300" />
                    </div>
                  )}
                </div>
              ))
            )}

            {loading && status && (
              <div className="flex items-center space-x-3 text-xs text-indigo-300 bg-indigo-950/40 border border-indigo-500/30 p-3 rounded-xl max-w-md animate-pulse shadow-sm">
                <Loader2 className="w-4 h-4 animate-spin shrink-0 text-indigo-400" />
                <span>{status}</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </main>

          {/* Research Input Form */}
          <footer className="p-4 border-t border-slate-800/80 bg-slate-950/80 backdrop-blur sticky bottom-0 z-20">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="max-w-4xl mx-auto flex gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about 5G Core (TS 23), Security (TS 33), Charging (TS 32), RRC (TS 38.331), LTE (TS 36)..."
                disabled={loading}
                className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition disabled:opacity-50 text-slate-100 placeholder-slate-500 shadow-inner"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-5 py-3 rounded-xl font-medium text-sm flex items-center gap-2 transition shadow-md shadow-indigo-950/50"
              >
                <Send className="w-4 h-4" />
                <span>Send</span>
              </button>
            </form>
          </footer>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODE 2: NEW FEATURE HLD AGENT (3-STAGE ENGINEERING WORKFLOW) */}
      {/* ========================================================================= */}
      {activeTab === "hld" && (
        <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
          {/* Left Panel: Feature Specification & Scope Controls */}
          <aside className="w-full md:w-[380px] lg:w-[420px] border-r border-slate-800/80 bg-slate-950/60 p-4 md:p-6 overflow-y-auto space-y-6 shrink-0">
            <div>
              <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-400" />
                <span>Feature Design Input</span>
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Configure feature requirements for 3-stage High-Level Design (HLD) generation.
              </p>
            </div>

            {/* Built-in Presets */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                1-Click Study Presets
              </label>
              <div className="grid grid-cols-1 gap-2">
                {HLD_PRESETS.map((preset, idx) => (
                  <button
                    key={idx}
                    onClick={() => applyPreset(preset)}
                    className="text-left p-2.5 rounded-xl bg-slate-900/80 hover:bg-slate-850 border border-slate-800 hover:border-indigo-500/50 transition group"
                  >
                    <div className="text-xs font-semibold text-indigo-300 group-hover:text-indigo-200 flex items-center justify-between">
                      <span>{preset.title}</span>
                      <ArrowRight className="w-3 h-3 text-slate-500 group-hover:text-indigo-400 transition" />
                    </div>
                    <p className="text-[11px] text-slate-400 line-clamp-2 mt-0.5">{preset.description}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Target Feature Name */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300">
                Target Feature Name <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={hldFeature}
                onChange={(e) => setHldFeature(e.target.value)}
                placeholder="e.g. Regenerative Satellite Payloads for NTN"
                disabled={hldLoading}
                className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition text-slate-100 placeholder-slate-500"
              />
            </div>

            {/* Scope / Architectural Notes */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300">
                Scope & Architectural Constraints (Optional)
              </label>
              <textarea
                value={hldDescription}
                onChange={(e) => setHldDescription(e.target.value)}
                rows={3}
                placeholder="Specify target nodes (gNB-DU on payload, ISL links), latency constraints, or focused interfaces..."
                disabled={hldLoading}
                className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition text-slate-100 placeholder-slate-500 resize-none leading-relaxed"
              />
            </div>

            {/* Target Releases Filter */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 flex justify-between items-center">
                <span>Target 3GPP Releases</span>
                <span className="text-[11px] text-slate-500 font-normal">{hldReleases.length} selected</span>
              </label>
              <div className="flex flex-wrap gap-1.5">
                {ALL_RELEASES.map((rel) => {
                  const isSelected = hldReleases.includes(rel);
                  return (
                    <button
                      key={rel}
                      type="button"
                      onClick={() => toggleRelease(rel)}
                      disabled={hldLoading}
                      className={`px-2.5 py-1 text-xs rounded-lg border transition font-mono ${
                        isSelected
                          ? "bg-indigo-600/30 text-indigo-200 border-indigo-500/50 shadow-sm"
                          : "bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200 hover:border-slate-700"
                      }`}
                    >
                      {rel}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Launch Button */}
            <button
              onClick={handleGenerateHLD}
              disabled={hldLoading || !hldFeature.trim()}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white py-3 rounded-xl font-semibold text-xs flex items-center justify-center gap-2 transition shadow-lg shadow-indigo-950/60"
            >
              {hldLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Synthesizing HLD Pipeline…</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  <span>Generate New Feature HLD</span>
                </>
              )}
            </button>
          </aside>

          {/* Right Panel: Live 3-Stage Progress & Master HLD Deliverable */}
          <section className="flex-1 flex flex-col min-h-0 bg-slate-950 overflow-y-auto p-4 md:p-6 space-y-6">
            {/* 3-Stage Visual Pipeline Stepper */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Stage 1 Box */}
              <div
                className={`p-3.5 rounded-xl border transition ${
                  hldCurrentStage === 1
                    ? "bg-indigo-950/40 border-indigo-500/60 shadow-md shadow-indigo-950"
                    : hldCurrentStage > 1
                    ? "bg-slate-900/80 border-emerald-500/40"
                    : "bg-slate-900/40 border-slate-800/80 opacity-60"
                }`}
              >
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-semibold text-slate-300">Stage 1: Impact Scanner</span>
                  {hldCurrentStage > 1 ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : hldCurrentStage === 1 ? (
                    <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
                  ) : (
                    <span className="text-[10px] text-slate-500 font-mono">Pending</span>
                  )}
                </div>
                <p className="text-[11px] text-slate-400">Maps impacted specs across Core, RAN, Security & Management.</p>
              </div>

              {/* Stage 2 Box */}
              <div
                className={`p-3.5 rounded-xl border transition ${
                  hldCurrentStage === 2
                    ? "bg-indigo-950/40 border-indigo-500/60 shadow-md shadow-indigo-950"
                    : hldCurrentStage > 2
                    ? "bg-slate-900/80 border-emerald-500/40"
                    : "bg-slate-900/40 border-slate-800/80 opacity-60"
                }`}
              >
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-semibold text-slate-300">Stage 2: Interface Extractor</span>
                  {hldCurrentStage > 2 ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : hldCurrentStage === 2 ? (
                    <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
                  ) : (
                    <span className="text-[10px] text-slate-500 font-mono">Pending</span>
                  )}
                </div>
                <p className="text-[11px] text-slate-400">Extracts Uu, Xn, F1, SBI deltas, IEs, timers, and release progression.</p>
              </div>

              {/* Stage 3 Box */}
              <div
                className={`p-3.5 rounded-xl border transition ${
                  hldCurrentStage === 3
                    ? "bg-indigo-950/40 border-indigo-500/60 shadow-md shadow-indigo-950"
                    : hldCurrentStage === 4
                    ? "bg-slate-900/80 border-emerald-500/40"
                    : "bg-slate-900/40 border-slate-800/80 opacity-60"
                }`}
              >
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-semibold text-slate-300">Stage 3: Lead Architect</span>
                  {hldCurrentStage === 4 ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : hldCurrentStage === 3 ? (
                    <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
                  ) : (
                    <span className="text-[10px] text-slate-500 font-mono">Pending</span>
                  )}
                </div>
                <p className="text-[11px] text-slate-400">Synthesizes master HLD with architecture diagrams & open questions.</p>
              </div>
            </div>

            {/* Live Progress Banner */}
            {hldLoading && hldStatus && (
              <div className="flex items-center space-x-3 text-xs text-indigo-300 bg-indigo-950/40 border border-indigo-500/40 p-3.5 rounded-xl animate-pulse shadow-sm">
                <Loader2 className="w-4 h-4 animate-spin shrink-0 text-indigo-400" />
                <span>{hldStatus}</span>
              </div>
            )}

            {/* Empty State when no HLD generated */}
            {!hldDocument && !hldLoading && (
              <div className="h-96 flex flex-col items-center justify-center text-center space-y-4 border border-dashed border-slate-800/80 rounded-2xl p-8 bg-slate-950/40">
                <div className="p-4 bg-slate-900 rounded-2xl border border-slate-800 text-indigo-400">
                  <FileText className="w-8 h-8" />
                </div>
                <div className="max-w-md space-y-1.5">
                  <h3 className="text-base font-bold text-slate-200">No High-Level Design Generated Yet</h3>
                  <p className="text-xs text-slate-400">
                    Select a 1-click study preset or enter a new telecom feature on the left, then click <strong>"Generate New Feature HLD"</strong>.
                  </p>
                </div>
              </div>
            )}

            {/* Intermediate Artifact Accordions (Stage 1 & Stage 2) */}
            {impactMap && (
              <div className="border border-slate-800 rounded-xl bg-slate-950/70 overflow-hidden shadow-sm">
                <button
                  onClick={() => setOpenImpact(!openImpact)}
                  className="w-full px-4 py-3 text-xs flex items-center justify-between text-slate-300 hover:text-white bg-slate-900/60 transition"
                >
                  <span className="font-mono flex items-center gap-2 text-indigo-300">
                    <Radio className="w-4 h-4" />
                    <span>Stage 1: Specifications Impact Map (Intermediary Artifact)</span>
                  </span>
                  {openImpact ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
                {openImpact && (
                  <div className="p-4 text-xs font-mono text-slate-300 bg-black/60 border-t border-slate-800 max-h-80 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                    {impactMap}
                  </div>
                )}
              </div>
            )}

            {parametersLedger && (
              <div className="border border-slate-800 rounded-xl bg-slate-950/70 overflow-hidden shadow-sm">
                <button
                  onClick={() => setOpenLedger(!openLedger)}
                  className="w-full px-4 py-3 text-xs flex items-center justify-between text-slate-300 hover:text-white bg-slate-900/60 transition"
                >
                  <span className="font-mono flex items-center gap-2 text-indigo-300">
                    <Cpu className="w-4 h-4" />
                    <span>Stage 2: Technical Parameters & Interfaces Ledger (Intermediary Artifact)</span>
                  </span>
                  {openLedger ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
                {openLedger && (
                  <div className="p-4 text-xs font-mono text-slate-300 bg-black/60 border-t border-slate-800 max-h-80 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                    {parametersLedger}
                  </div>
                )}
              </div>
            )}

            {/* Master HLD Deliverable */}
            {hldDocument && (
              <div className="space-y-4">
                {/* HLD Document Header Actions */}
                <div className="flex items-center justify-between bg-slate-900/90 border border-slate-800 p-3 rounded-xl">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
                    <FileCheck className="w-4 h-4 text-emerald-400" />
                    <span>Master High-Level Design (HLD) Document</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={copyHLD}
                      className="flex items-center gap-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-750 text-slate-300 hover:text-white text-xs rounded-lg transition border border-slate-700/60"
                    >
                      {copiedHld ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copiedHld ? "Copied" : "Copy Markdown"}</span>
                    </button>
                    <button
                      onClick={downloadHLD}
                      className="flex items-center gap-1 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded-lg transition shadow-sm"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Download .md</span>
                    </button>
                  </div>
                </div>

                {/* Rendered HLD Markdown */}
                <div className="p-6 bg-slate-900/80 border border-slate-800 rounded-2xl text-sm leading-relaxed text-slate-200 shadow-xl overflow-hidden max-w-full">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      table: ({ node, ...props }) => (
                        <div className="my-4 overflow-x-auto border border-slate-700/80 rounded-xl shadow-lg bg-slate-950/60 max-w-full">
                          <table className="w-full text-left border-collapse text-xs md:text-sm" {...props} />
                        </div>
                      ),
                      thead: ({ node, ...props }) => (
                        <thead className="bg-indigo-950/50 text-indigo-200 border-b border-slate-700 font-semibold" {...props} />
                      ),
                      th: ({ node, ...props }) => (
                        <th className="py-3 px-4 font-semibold text-slate-200 uppercase tracking-wider text-[11px] border-r border-slate-800/80 last:border-r-0" {...props} />
                      ),
                      tbody: ({ node, ...props }) => (
                        <tbody className="divide-y divide-slate-800/80" {...props} />
                      ),
                      tr: ({ node, ...props }) => (
                        <tr className="hover:bg-slate-850/60 transition-colors" {...props} />
                      ),
                      td: ({ node, ...props }) => (
                        <td className="py-2.5 px-4 text-slate-300 border-r border-slate-800/60 last:border-r-0 align-top leading-relaxed" {...props} />
                      ),
                      h1: ({ node, ...props }) => (
                        <h1 className="text-xl md:text-2xl font-bold text-slate-100 mt-6 mb-3 border-b border-slate-800 pb-2.5" {...props} />
                      ),
                      h2: ({ node, ...props }) => (
                        <h2 className="text-lg md:text-xl font-bold text-indigo-300 mt-6 mb-2.5" {...props} />
                      ),
                      h3: ({ node, ...props }) => (
                        <h3 className="text-base font-semibold text-slate-200 mt-4 mb-2" {...props} />
                      ),
                      p: ({ node, ...props }) => (
                        <p className="mb-3 leading-relaxed text-slate-300 last:mb-0" {...props} />
                      ),
                      ul: ({ node, ...props }) => (
                        <ul className="list-disc list-inside space-y-1.5 my-2.5 text-slate-300" {...props} />
                      ),
                      ol: ({ node, ...props }) => (
                        <ol className="list-decimal list-inside space-y-1.5 my-2.5 text-slate-300" {...props} />
                      ),
                      li: ({ node, ...props }) => (
                        <li className="leading-relaxed text-slate-300" {...props} />
                      ),
                      blockquote: ({ node, ...props }) => (
                        <blockquote className="my-3 pl-4 border-l-2 border-indigo-500 text-slate-400 italic bg-indigo-950/20 py-2 rounded-r-lg" {...props} />
                      ),
                      code: ({ node, className, children, ...props }: any) => {
                        const codeString = String(children || "");
                        const hasLang = Boolean(className && /language-/.test(className));
                        const hasNewlines = codeString.includes("\n");

                        if (!hasLang && !hasNewlines) {
                          return (
                            <code
                              className="bg-slate-800/90 text-indigo-300 px-1.5 py-0.5 rounded text-[12px] font-mono border border-slate-700/60 break-all inline"
                              {...props}
                            >
                              {children}
                            </code>
                          );
                        }

                        return <CodeBlock className={className}>{children}</CodeBlock>;
                      },
                    }}
                  >
                    {hldDocument}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}