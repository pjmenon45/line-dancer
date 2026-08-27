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
  "What does TS 38.331 cover regarding RRC connection establishment? Include a Mermaid sequence diagram and table of timers.",
  "Summarize the main changes related to RedCap UEs in TS 38 series across recent releases. Show a comparison table.",
  "Extract implementation requirements for network slicing in NR (TS 38 series). Include an architecture diagram.",
];

function CodeBlock({ className, children }: { className?: string; children: React.ReactNode }) {
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className || "");
  const language = match ? match[1] : "";
  const codeString = String(children).replace(/\n$/, "");

  // Render Mermaid diagrams directly
  if (language === "mermaid") {
    return <Mermaid chart={codeString} />;
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(codeString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-slate-700/70 bg-slate-950/80 shadow-md">
      <div className="px-3.5 py-1.5 bg-slate-900 border-b border-slate-800 text-[11px] text-slate-400 font-mono flex justify-between items-center">
        <span className="font-semibold text-slate-300 uppercase tracking-wider">{language || "text"}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-indigo-300 transition"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <pre className="p-3.5 text-xs overflow-x-auto font-mono text-slate-200 leading-relaxed">
        <code>{codeString}</code>
      </pre>
    </div>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [openEvidence, setOpenEvidence] = useState<{ [key: number]: boolean }>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, status]);

  const toggleEvidence = (idx: number) => {
    setOpenEvidence((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

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
          series: ["38"],
          releases: ["Rel-16", "Rel-17", "Rel-18", "Rel-19"],
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

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100 selection:bg-indigo-500 selection:text-white">
      {/* Header */}
      <header className="px-6 py-4 border-b border-slate-800/80 flex items-center justify-between bg-slate-950/80 backdrop-blur sticky top-0 z-20">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-indigo-600/20 text-indigo-400 rounded-xl border border-indigo-500/30 shadow-inner">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-semibold text-base md:text-lg flex items-center gap-2">
              <span>3GPP Standards Research & Gap Analysis</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                Rel-15 to Rel-19
              </span>
            </h1>
            <p className="text-xs text-slate-400">Sequential 2-Agent Orchestration with TSpec-LLM MCP & Mermaid Rendering</p>
          </div>
        </div>
        <div className="hidden sm:flex items-center space-x-2 text-xs bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-full">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="text-slate-300 font-mono">{BACKEND_URL.replace("https://", "")}</span>
        </div>
      </header>

      {/* Chat Messages */}
      <main className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 max-w-4xl w-full mx-auto">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-6 py-12">
            <div className="p-4 bg-indigo-950/40 border border-indigo-500/30 rounded-2xl shadow-xl shadow-indigo-950/50">
              <Sparkles className="w-8 h-8 text-indigo-400" />
            </div>
            <div className="max-w-md space-y-2">
              <h2 className="text-xl font-bold">Query 3GPP Technical Specifications</h2>
              <p className="text-sm text-slate-400">
                The Researcher agent queries official 3GPP TS specifications, and the Analyst agent formats reports with comparison tables, sequence diagrams, and citations.
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
              <div className={`max-w-[90%] md:max-w-[85%] space-y-3 ${m.role === "user" ? "items-end" : "items-start"}`}>
                <div
                  className={`p-4 md:p-5 rounded-2xl text-sm leading-relaxed ${
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
                          <div className="my-4 overflow-x-auto border border-slate-700/80 rounded-xl shadow-lg bg-slate-950/60">
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
                        blockquote: ({ node, ...props }) => (
                          <blockquote className="my-3 pl-4 border-l-2 border-indigo-500 text-slate-400 italic bg-indigo-950/20 py-2 rounded-r-lg" {...props} />
                        ),
                        code: ({ node, inline, className, children, ...props }: any) => {
                          if (inline) {
                            return (
                              <code className="bg-slate-800 text-indigo-300 px-1.5 py-0.5 rounded text-[13px] font-mono border border-slate-700/60" {...props}>
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
                  <div className="border border-slate-800 rounded-xl bg-slate-950/60 overflow-hidden shadow-sm">
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

        {/* Live Status Indicator during streaming */}
        {loading && status && (
          <div className="flex items-center space-x-3 text-xs text-indigo-300 bg-indigo-950/40 border border-indigo-500/30 p-3 rounded-xl max-w-md animate-pulse shadow-sm">
            <Loader2 className="w-4 h-4 animate-spin shrink-0 text-indigo-400" />
            <span>{status}</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      {/* Input Form */}
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
            placeholder="Ask about TS 38.331, RedCap, 5G Slicing, RRC procedures, timers, diagrams..."
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
  );
}