"use client";

import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send, Bot, User, ChevronDown, ChevronUp, Sparkles, Loader2 } from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "https://line-dancer.onrender.com";

interface Message {
  role: "user" | "assistant";
  content: string;
  evidence?: string;
  stage?: string;
}

const SAMPLE_QUESTIONS = [
  "What does TS 38.331 cover regarding RRC connection establishment?",
  "Summarize the main changes related to RedCap UEs in TS 38 series across recent releases.",
  "Extract implementation requirements for network slicing in NR (TS 38 series).",
];

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
    <div className="flex flex-col h-screen bg-slate-900 text-slate-100">
      {/* Header */}
      <header className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/50 backdrop-blur">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-lg border border-indigo-500/30">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-semibold text-lg">3GPP Standards Research & Gap Analysis</h1>
            <p className="text-xs text-slate-400">Powered by 2-Agent Multi-Agent Workflow & 3GPP MCP</p>
          </div>
        </div>
        <div className="flex items-center space-x-2 text-xs">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="text-slate-400">Backend: {BACKEND_URL.replace("https://", "")}</span>
        </div>
      </header>

      {/* Chat Messages */}
      <main className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 max-w-4xl w-full mx-auto">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-6 py-12">
            <div className="p-4 bg-indigo-950/40 border border-indigo-500/20 rounded-2xl">
              <Sparkles className="w-8 h-8 text-indigo-400" />
            </div>
            <div className="max-w-md space-y-2">
              <h2 className="text-xl font-bold">Ask anything about 3GPP Standards</h2>
              <p className="text-sm text-slate-400">
                The Researcher agent queries official 3GPP TS specifications, and the Analyst agent synthesizes requirements and changes.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2 w-full max-w-lg text-left">
              {SAMPLE_QUESTIONS.map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSend(q)}
                  className="p-3 text-xs bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 rounded-xl transition text-slate-300 hover:text-white"
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
                <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 text-indigo-400" />
                </div>
              )}
              <div className={`max-w-[85%] space-y-3 ${m.role === "user" ? "items-end" : "items-start"}`}>
                <div
                  className={`p-4 rounded-2xl text-sm leading-relaxed ${
                    m.role === "user"
                      ? "bg-indigo-600 text-white rounded-br-none"
                      : "bg-slate-800/80 border border-slate-700/60 text-slate-200 rounded-bl-none prose prose-invert max-w-none"
                  }`}
                >
                  {m.role === "user" ? (
                    m.content
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                  )}
                </div>

                {/* Collapsible Evidence Pack */}
                {m.evidence && (
                  <div className="border border-slate-700/50 rounded-xl bg-slate-950/40 overflow-hidden">
                    <button
                      onClick={() => toggleEvidence(idx)}
                      className="w-full px-3 py-2 text-xs flex items-center justify-between text-slate-400 hover:text-slate-200 bg-slate-800/30"
                    >
                      <span className="font-mono">📑 Researcher Evidence Pack (3GPP Raw Excerpts)</span>
                      {openEvidence[idx] ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                    {openEvidence[idx] && (
                      <div className="p-3 text-xs font-mono text-slate-300 bg-black/40 border-t border-slate-800 max-h-60 overflow-y-auto whitespace-pre-wrap">
                        {m.evidence}
                      </div>
                    )}
                  </div>
                )}
              </div>
              {m.role === "user" && (
                <div className="w-8 h-8 rounded-lg bg-slate-700/40 border border-slate-600 flex items-center justify-center shrink-0">
                  <User className="w-4 h-4 text-slate-300" />
                </div>
              )}
            </div>
          ))
        )}

        {/* Live Status Indicator during streaming */}
        {loading && status && (
          <div className="flex items-center space-x-3 text-xs text-indigo-400 bg-indigo-950/30 border border-indigo-500/20 p-3 rounded-xl max-w-md animate-pulse">
            <Loader2 className="w-4 h-4 animate-spin shrink-0" />
            <span>{status}</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      {/* Input Form */}
      <footer className="p-4 border-t border-slate-800 bg-slate-950/50 backdrop-blur">
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
            placeholder="Ask about TS 38.331, RedCap, 5G Slicing, RRC..."
            disabled={loading}
            className="flex-1 bg-slate-800/80 border border-slate-700 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-indigo-500 transition disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-5 py-3 rounded-xl font-medium text-sm flex items-center gap-2 transition"
          >
            <Send className="w-4 h-4" />
            <span>Send</span>
          </button>
        </form>
      </footer>
    </div>
  );
}