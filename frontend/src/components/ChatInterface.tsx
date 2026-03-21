/* ── Chat Interface — TAO conversational AI ── */
"use client";

import { useState, useRef, useEffect } from "react";
import { MessageSquare, Send, Bot, User, Wrench, Loader2 } from "lucide-react";
import { useTrafficStore } from "@/lib/store";
import { api } from "@/lib/api";
import { cn, formatTime } from "@/lib/utils";
import type { ChatMessage } from "@/lib/types";

export default function ChatInterface() {
  const messages = useTrafficStore((s) => s.messages);
  const addMessage = useTrafficStore((s) => s.addMessage);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    const userMsg: ChatMessage = {
      role: "user",
      content: trimmed,
      timestamp: new Date().toISOString(),
      tool_calls: [],
      thinking: "",
    };
    addMessage(userMsg);
    setInput("");
    setLoading(true);

    try {
      const res = await api.sendChat(trimmed);
      const botMsg: ChatMessage = {
        role: "assistant",
        content: res.response,
        timestamp: new Date().toISOString(),
        tool_calls: res.tool_calls || [],
        thinking: res.thinking || "",
      };
      addMessage(botMsg);
    } catch {
      addMessage({
        role: "assistant",
        content: "Connection error. Please try again.",
        timestamp: new Date().toISOString(),
        tool_calls: [],
        thinking: "",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full p-1">
      <div className="flex items-center gap-2 mb-3">
        <MessageSquare className="w-4 h-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">
          AI Chat — Narrative Agent
        </h3>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-3 mb-3 pr-1"
        style={{ maxHeight: "calc(100vh - 320px)" }}
      >
        {messages.length === 0 && (
          <div className="text-center py-8 text-muted">
            <Bot className="w-8 h-8 mx-auto mb-2 text-slate-300" />
            <p className="text-xs">Ask about current traffic conditions,</p>
            <p className="text-xs">incident status, or diversion routes.</p>
            <div className="mt-3 space-y-1.5">
              {[
                "What's the current traffic situation?",
                "How bad is the congestion on Atlantic Ave?",
                "What's the diversion route status?",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  className="block w-full text-left text-[11px] text-primary hover:bg-primary/5 rounded px-2 py-1 transition-colors"
                >
                  &ldquo;{q}&rdquo;
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={cn(
              "flex gap-2",
              msg.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            {msg.role === "assistant" && (
              <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Bot className="w-3.5 h-3.5 text-primary" />
              </div>
            )}
            <div
              className={cn(
                "max-w-[85%] rounded-lg px-3 py-2",
                msg.role === "user"
                  ? "bg-primary text-white"
                  : "bg-slate-50 border border-border"
              )}
            >
              <p className="text-xs leading-relaxed whitespace-pre-wrap">
                {msg.content}
              </p>

              {/* Tool calls */}
              {msg.tool_calls?.length > 0 && (
                <div className="mt-2 space-y-1">
                  {msg.tool_calls.map((tc, j) => (
                    <div
                      key={j}
                      className="flex items-start gap-1 text-[10px] text-muted bg-white/50 rounded px-1.5 py-1"
                    >
                      <Wrench className="w-3 h-3 mt-0.5 flex-shrink-0" />
                      <span>
                        <strong>{tc.tool}</strong>({tc.args}) → {tc.result.slice(0, 80)}
                        {tc.result.length > 80 ? "…" : ""}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <p className="text-[9px] mt-1 opacity-60">
                {formatTime(msg.timestamp)}
              </p>
            </div>
            {msg.role === "user" && (
              <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mt-0.5">
                <User className="w-3.5 h-3.5 text-white" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-muted">
            <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">
              <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />
            </div>
            <span className="text-xs">Thinking…</span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex gap-2 border-t border-border pt-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask about traffic conditions…"
          className="flex-1 text-xs border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
          disabled={loading}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          className="px-3 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
