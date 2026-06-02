import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Trash2, ChevronRight, Layers, FileStack, Cpu } from "lucide-react";
import Dropzone from "./components/Dropzone";
import ChatMessage from "./components/ChatMessage";
import { createSession, uploadFiles, queryStream, deleteSession } from "./api";

const EXAMPLE_QUESTIONS = [
  "What is this document about?",
  "Summarise the key requirements",
  "What skills or qualifications are needed?",
  "Compare the main points across documents",
];

export default function App() {
  const [sessionId, setSessionId] = useState(null);
  const [files, setFiles] = useState([]);
  const [indexing, setIndexing] = useState(false);
  const [indexResult, setIndexResult] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const tokenBufferRef = useRef("");
  const rafRef = useRef(null);
  const textareaRef = useRef(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [input]);

  // Persist session + messages in localStorage
  useEffect(() => {
    if (sessionId) localStorage.setItem("omni_session", sessionId);
  }, [sessionId]);
  useEffect(() => {
    if (messages.length) localStorage.setItem("omni_messages", JSON.stringify(messages));
  }, [messages]);
  // Restore on mount (best-effort — session may have expired)
  useEffect(() => {
    const savedMessages = localStorage.getItem("omni_messages");
    const savedSession = localStorage.getItem("omni_session");
    if (savedMessages && savedSession) {
      try {
        const parsed = JSON.parse(savedMessages);
        // Only restore if last message isn't mid-stream
        if (!parsed[parsed.length - 1]?.streaming) {
          setMessages(parsed);
          setSessionId(savedSession);
        }
      } catch { /* ignore */ }
    }
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleIndex = async () => {
    if (!files.length) return;
    setIndexing(true);
    try {
      const sid = await createSession();
      setSessionId(sid);
      const result = await uploadFiles(sid, files);
      setIndexResult(result);
      setMessages([{
        role: "assistant",
        content: `Indexed ${result.files.length} file(s) into your session. Ask me anything about your documents.`,
      }]);
    } catch (e) {
      setIndexResult({ error: e.message });
    } finally {
      setIndexing(false);
    }
  };

  const handleQuery = async () => {
    const q = input.trim();
    if (!q || !sessionId || loading) return;
    setInput("");

    // Add user message
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);

    // Add empty assistant message that we'll stream into
    setMessages((prev) => [...prev, { role: "assistant", content: "", streaming: true }]);

    // Flush buffered tokens to state on each animation frame
    const flushBuffer = () => {
      if (tokenBufferRef.current) {
        const chunk = tokenBufferRef.current;
        tokenBufferRef.current = "";
        setMessages((prev) => {
          const updated = [...prev];
          const last = { ...updated[updated.length - 1] };
          last.content += chunk;
          updated[updated.length - 1] = last;
          return updated;
        });
      }
      rafRef.current = requestAnimationFrame(flushBuffer);
    };
    rafRef.current = requestAnimationFrame(flushBuffer);

    try {
      await queryStream(
        sessionId,
        q,
        // onToken — buffer tokens, flushed by rAF above
        (token) => { tokenBufferRef.current += token; },
        // onDone — cancel rAF, flush remaining, attach sources
        (meta) => {
          cancelAnimationFrame(rafRef.current);
          const remaining = tokenBufferRef.current;
          tokenBufferRef.current = "";
          setMessages((prev) => {
            const updated = [...prev];
            const last = { ...updated[updated.length - 1] };
            if (remaining) last.content += remaining;
            last.streaming = false;
            if (meta) {
              last.sources = meta.sources;
              last.hops = meta.hops;
            }
            updated[updated.length - 1] = last;
            return updated;
          });
          setLoading(false);
        }
      );
    } catch (e) {
      cancelAnimationFrame(rafRef.current);
      tokenBufferRef.current = "";
      setMessages((prev) => {
        const updated = [...prev];
        const last = { ...updated[updated.length - 1] };
        last.content = `Error: ${e.message}`;
        last.streaming = false;
        updated[updated.length - 1] = last;
        return updated;
      });
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (sessionId) await deleteSession(sessionId).catch(() => {});
    localStorage.removeItem("omni_session");
    localStorage.removeItem("omni_messages");
    setSessionId(null);
    setFiles([]);
    setIndexResult(null);
    setMessages([]);
    setInput("");
  };

  const ready = !!sessionId && !indexing;
  const userTurns = messages.filter(m => m.role === "user").length;

  const S = {
    wrap: { display: "flex", height: "100vh", background: "#05050d", color: "#e2e8f0", fontFamily: "'Inter', sans-serif", overflow: "hidden" },

    // sidebar
    sidebar: { width: 268, flexShrink: 0, display: "flex", flexDirection: "column", background: "#08080f", borderRight: "1px solid #111120", position: "relative", overflow: "hidden" },
    sidebarGlow: { position: "absolute", top: -80, left: -80, width: 240, height: 240, borderRadius: "50%", background: "radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)", pointerEvents: "none" },
    brand: { padding: "20px 18px 16px", borderBottom: "1px solid #111120", display: "flex", alignItems: "center", gap: 10 },
    logoWrap: { width: 34, height: 34, borderRadius: 10, background: "linear-gradient(135deg,#4338ca,#7c3aed)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, boxShadow: "0 4px 14px rgba(99,102,241,0.35)" },
    scrollArea: { flex: 1, overflowY: "auto", padding: "16px 14px", display: "flex", flexDirection: "column", gap: 16 },
    label: { fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "#1e293b", marginBottom: 8 },
    indexBtn: (active) => ({
      width: "100%", padding: "10px 0", borderRadius: 10, border: "none", cursor: active ? "pointer" : "not-allowed",
      fontSize: 13, fontWeight: 500, display: "flex", alignItems: "center", justifyContent: "center", gap: 7,
      background: active ? "linear-gradient(135deg,#4338ca,#6366f1)" : "rgba(255,255,255,0.03)",
      color: active ? "#fff" : "#334155",
      boxShadow: active ? "0 4px 20px rgba(99,102,241,0.3)" : "none",
      transition: "all 0.2s", opacity: active ? 1 : 0.6,
    }),
    fileChip: { display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(255,255,255,0.02)", border: "1px solid #111120", borderRadius: 8, padding: "6px 10px" },
    sidebarFooter: { padding: "10px 14px", borderTop: "1px solid #111120" },
    clearBtn: { width: "100%", display: "flex", alignItems: "center", gap: 8, padding: "8px 10px", borderRadius: 8, border: "none", cursor: "pointer", background: "none", fontSize: 12, color: "#334155", transition: "all 0.15s" },

    // main
    main: { flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" },
    bgGlow1: { position: "absolute", top: "10%", right: "5%", width: 400, height: 400, borderRadius: "50%", background: "radial-gradient(circle, rgba(99,102,241,0.04) 0%, transparent 70%)", pointerEvents: "none" },
    bgGlow2: { position: "absolute", bottom: "20%", left: "10%", width: 300, height: 300, borderRadius: "50%", background: "radial-gradient(circle, rgba(124,58,237,0.03) 0%, transparent 70%)", pointerEvents: "none" },
    topbar: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 24px", borderBottom: "1px solid #0f0f1a", backdropFilter: "blur(20px)", background: "rgba(5,5,13,0.8)", flexShrink: 0, position: "relative", zIndex: 1 },
    msgArea: { flex: 1, overflowY: "auto", padding: "32px 28px", display: "flex", flexDirection: "column", gap: 24, position: "relative", zIndex: 1 },
    inputWrap: { padding: "14px 24px 16px", borderTop: "1px solid #0f0f1a", background: "rgba(5,5,13,0.9)", backdropFilter: "blur(20px)", flexShrink: 0, position: "relative", zIndex: 1 },
    inputBox: (focused) => ({
      display: "flex", alignItems: "flex-end", gap: 10,
      background: "rgba(255,255,255,0.03)", border: `1px solid ${focused ? "rgba(99,102,241,0.4)" : "#111120"}`,
      borderRadius: 16, padding: "12px 14px", transition: "border-color 0.15s",
    }),
    sendBtn: (active) => ({
      flexShrink: 0, width: 34, height: 34, borderRadius: 10, border: "none", cursor: active ? "pointer" : "not-allowed",
      background: active ? "linear-gradient(135deg,#4338ca,#6366f1)" : "rgba(255,255,255,0.04)",
      display: "flex", alignItems: "center", justifyContent: "center",
      boxShadow: active ? "0 2px 12px rgba(99,102,241,0.4)" : "none",
      transition: "all 0.2s",
    }),
  };

  const [inputFocused, setInputFocused] = useState(false);

  return (
    <div style={S.wrap}>

      {/* ── Sidebar ── */}
      <aside style={S.sidebar}>
        <div style={S.sidebarGlow} />

        {/* Brand */}
        <div style={S.brand}>
          <div style={S.logoWrap}>
            <Layers size={16} color="white" />
          </div>
          <div>
            <p style={{ fontSize: 14, fontWeight: 600, color: "#f1f5f9", lineHeight: 1.2 }}>OmniMind</p>
            <p style={{ fontSize: 10, color: "#334155", marginTop: 1 }}>Multimodal RAG · Local</p>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 5, background: "rgba(52,211,153,0.08)", border: "1px solid rgba(52,211,153,0.15)", borderRadius: 6, padding: "3px 7px" }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: ready ? "#34d399" : "#334155" }} />
            <span style={{ fontSize: 10, color: ready ? "#34d399" : "#334155", fontWeight: 500 }}>{ready ? "Live" : "Idle"}</span>
          </div>
        </div>

        {/* Scroll area */}
        <div style={S.scrollArea}>
          <div>
            <p style={S.label}>Documents</p>
            <Dropzone files={files} onChange={setFiles} />
          </div>

          <button
            onClick={handleIndex}
            disabled={!files.length || indexing}
            style={S.indexBtn(files.length > 0 && !indexing)}
          >
            {indexing
              ? <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />Indexing…</>
              : <><FileStack size={14} />Index Documents</>
            }
          </button>

          {indexResult && !indexResult.error && (
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <p style={S.label}>Indexed</p>
              {indexResult.files.map((f, i) => (
                <div key={i} style={S.fileChip}>
                  <span style={{ fontSize: 11, color: "#64748b", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 150 }}>{f.file}</span>
                  <span style={{ fontSize: 10, fontWeight: 600, color: "#818cf8", background: "rgba(99,102,241,0.12)", padding: "2px 6px", borderRadius: 5, flexShrink: 0 }}>{f.chunks_indexed}</span>
                </div>
              ))}
            </div>
          )}

          {indexResult?.error && (
            <div style={{ fontSize: 11, color: "#f87171", background: "rgba(248,113,113,0.07)", border: "1px solid rgba(248,113,113,0.15)", borderRadius: 8, padding: "8px 10px" }}>
              {indexResult.error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={S.sidebarFooter}>
          {userTurns > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", background: "rgba(99,102,241,0.06)", borderRadius: 8, marginBottom: 8 }}>
              <Cpu size={11} color="#6366f1" />
              <span style={{ fontSize: 10, color: "#475569" }}>Memory · {Math.min(userTurns, 4)} turn{userTurns !== 1 ? "s" : ""} active</span>
            </div>
          )}
          {sessionId ? (
            <button
              style={S.clearBtn}
              onMouseEnter={e => { e.currentTarget.style.background = "rgba(248,113,113,0.07)"; e.currentTarget.style.color = "#f87171"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "none"; e.currentTarget.style.color = "#334155"; }}
              onClick={handleReset}
            >
              <Trash2 size={13} />
              Clear session
            </button>
          ) : (
            <p style={{ fontSize: 10, color: "#1e293b", textAlign: "center" }}>Private by default · No data leaves your machine</p>
          )}
        </div>
      </aside>

      {/* ── Main ── */}
      <main style={S.main}>
        <div style={S.bgGlow1} className="orb" />
        <div style={S.bgGlow2} className="orb" />

        {/* Topbar */}
        <div style={S.topbar}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 12, color: "#1e293b" }}>
              {ready
                ? <><span style={{ color: "#334155" }}>{indexResult?.files?.length ?? 0} file{indexResult?.files?.length !== 1 ? "s" : ""} indexed</span> · <span style={{ color: "#1e293b" }}>qwen2.5:7b</span></>
                : "Upload documents to begin"
              }
            </span>
          </div>
        </div>

        {/* Messages */}
        <div style={S.msgArea}>
          {messages.length === 0 && (
            <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 28, userSelect: "none" }}>
              {/* Hero */}
              <div style={{ textAlign: "center" }}>
                <div style={{ position: "relative", width: 64, height: 64, margin: "0 auto 20px" }}>
                  <div className="orb" style={{ position: "absolute", inset: -8, borderRadius: "50%", background: "radial-gradient(circle, rgba(99,102,241,0.2) 0%, transparent 70%)" }} />
                  <div style={{ width: 64, height: 64, borderRadius: 18, background: "linear-gradient(135deg,#1e1b4b,#312e81)", border: "1px solid rgba(99,102,241,0.3)", display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
                    <Layers size={28} color="#818cf8" />
                  </div>
                </div>
                <h2 style={{ fontSize: 22, fontWeight: 600, color: "#e2e8f0", marginBottom: 8 }}>
                  Ask anything about your{" "}
                  <span className="shimmer-text">documents</span>
                </h2>
                <p style={{ fontSize: 13, color: "#334155" }}>PDF · Images · Audio · CSV — grounded answers with cited sources</p>
              </div>

              {/* Capability chips */}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
                {["Hybrid BM25 + Semantic Search", "Streaming Responses", "Conversation Memory", "Multi-file Reasoning"].map(c => (
                  <span key={c} style={{ fontSize: 11, color: "#334155", border: "1px solid #111120", borderRadius: 99, padding: "4px 12px", background: "rgba(255,255,255,0.01)" }}>{c}</span>
                ))}
              </div>

              {ready && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, width: "100%", maxWidth: 520 }}>
                  {EXAMPLE_QUESTIONS.map(q => (
                    <button key={q}
                      onClick={() => { setInput(q); textareaRef.current?.focus(); }}
                      style={{ textAlign: "left", fontSize: 12, color: "#475569", background: "rgba(255,255,255,0.02)", border: "1px solid #111120", borderRadius: 12, padding: "11px 14px", cursor: "pointer", display: "flex", alignItems: "flex-start", gap: 8, transition: "all 0.15s" }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(99,102,241,0.3)"; e.currentTarget.style.color = "#94a3b8"; e.currentTarget.style.background = "rgba(99,102,241,0.04)"; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = "#111120"; e.currentTarget.style.color = "#475569"; e.currentTarget.style.background = "rgba(255,255,255,0.02)"; }}
                    >
                      <ChevronRight size={13} color="#1e293b" style={{ flexShrink: 0, marginTop: 1 }} />
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {messages.map((m, i) => <ChatMessage key={i} message={m} />)}

          {loading && messages[messages.length - 1]?.content === "" && (
            <div className="msg-enter" style={{ display: "flex", gap: 12 }}>
              <div style={{ width: 30, height: 30, borderRadius: 10, background: "linear-gradient(135deg,#4338ca,#7c3aed)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, boxShadow: "0 2px 12px rgba(99,102,241,0.25)" }}>
                <Loader2 size={14} color="white" style={{ animation: "spin 0.8s linear infinite" }} />
              </div>
              <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: "18px 18px 18px 4px", padding: "12px 16px", fontSize: 13, color: "#334155" }}>
                {userTurns > 1 ? "Rewriting from context…" : "Searching documents…"}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={S.inputWrap}>
          <div style={S.inputBox(inputFocused)}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setInputFocused(false)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleQuery(); } }}
              placeholder={ready ? "Ask about your documents…  ↵ to send" : "Index documents first…"}
              disabled={!ready || loading}
              rows={1}
              style={{ flex: 1, background: "none", border: "none", outline: "none", fontSize: 14, color: "#e2e8f0", resize: "none", lineHeight: 1.6, minHeight: 24, maxHeight: 160, overflow: "hidden", fontFamily: "inherit", opacity: !ready ? 0.35 : 1 }}
            />
            <button
              onClick={handleQuery}
              disabled={!ready || !input.trim() || loading}
              style={S.sendBtn(ready && !!input.trim() && !loading)}
            >
              <Send size={14} color={ready && input.trim() ? "white" : "#334155"} />
            </button>
          </div>
          <p style={{ fontSize: 10, color: "#0f0f1a", textAlign: "center", marginTop: 8 }}>
            Local inference · Your documents never leave this machine
          </p>
        </div>
      </main>
    </div>
  );
}
