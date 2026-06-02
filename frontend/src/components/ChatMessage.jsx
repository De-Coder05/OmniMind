import SourceCard from "./SourceCard";
import { Bot, Copy, Check, Files } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState } from "react";

/* ─── Citation rendering ─── */
const CITE_RE = /\(\[(\d+)\]\)|\[(\d+)\]/g;
const preprocess = (t) => t.replace(CITE_RE, (_, a, b) => `§${a ?? b}§`);

function Badge({ num }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      minWidth: "1.1rem", height: "1.1rem", padding: "0 3px",
      borderRadius: 4, fontSize: 9, fontWeight: 700, margin: "0 2px",
      background: "rgba(129,140,248,0.2)", color: "#a5b4fc", verticalAlign: "middle",
    }}>{num}</span>
  );
}

function withBadges(children) {
  const process = (str, k) =>
    str.split(/(§\d+§)/g).map((p, i) => {
      const m = p.match(/^§(\d+)§$/);
      return m ? <Badge key={`${k}-${i}`} num={m[1]} /> : p;
    });
  if (typeof children === "string") return process(children, 0);
  if (Array.isArray(children)) return children.map((c, i) => typeof c === "string" ? process(c, i) : c);
  return children;
}

function MD({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p:      ({ children }) => <p style={{ marginBottom: 10, lineHeight: 1.75, lastChild: { marginBottom: 0 } }}>{withBadges(children)}</p>,
        ul:     ({ children }) => <ul style={{ paddingLeft: 18, marginBottom: 10, display: "flex", flexDirection: "column", gap: 4 }}>{children}</ul>,
        ol:     ({ children }) => <ol style={{ paddingLeft: 18, marginBottom: 10, display: "flex", flexDirection: "column", gap: 4 }}>{children}</ol>,
        li:     ({ children }) => <li style={{ lineHeight: 1.7, color: "#e2e8f0" }}>{withBadges(children)}</li>,
        strong: ({ children }) => <strong style={{ color: "#f1f5f9", fontWeight: 600 }}>{withBadges(children)}</strong>,
        code:   ({ children }) => <code style={{ background: "rgba(129,140,248,0.12)", color: "#a5b4fc", padding: "1px 6px", borderRadius: 4, fontSize: "0.9em", fontFamily: "monospace" }}>{children}</code>,
        h3:     ({ children }) => <h3 style={{ color: "#f1f5f9", fontWeight: 600, fontSize: 13, marginBottom: 8, marginTop: 14 }}>{children}</h3>,
      }}
    >{preprocess(content || "")}</ReactMarkdown>
  );
}

/* ─── Copy button ─── */
function CopyBtn({ text }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 2000); }}
      style={{
        background: "rgba(255,255,255,0.04)", border: "1px solid #1a1a2e",
        borderRadius: 7, padding: "4px 8px", cursor: "pointer",
        display: "flex", alignItems: "center", gap: 4,
        fontSize: 11, color: done ? "#34d399" : "#475569",
        transition: "all 0.15s",
      }}
      onMouseEnter={e => { e.currentTarget.style.background = "rgba(255,255,255,0.07)"; e.currentTarget.style.color = "#94a3b8"; }}
      onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.04)"; e.currentTarget.style.color = done ? "#34d399" : "#475569"; }}
    >
      {done ? <Check size={11} /> : <Copy size={11} />}
      {done ? "Copied" : "Copy"}
    </button>
  );
}

/* ─── Group by file ─── */
function groupByFile(sources) {
  const m = {};
  sources.forEach((s, i) => {
    const f = s.metadata?.source || "Unknown";
    if (!m[f]) m[f] = [];
    m[f].push({ ...s, globalIndex: i });
  });
  return m;
}

export default function ChatMessage({ message }) {
  const isUser = message.role === "user";
  const sources = message.sources || [];
  const grouped = groupByFile(sources);
  const multiFile = Object.keys(grouped).length > 1;

  return (
    <div className="msg-enter" style={{ display: "flex", gap: 12, flexDirection: isUser ? "row-reverse" : "row" }}>
      {/* Avatar */}
      {!isUser && (
        <div style={{
          width: 30, height: 30, borderRadius: 10, flexShrink: 0, marginTop: 2,
          background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 2px 12px rgba(99,102,241,0.3)",
        }}>
          <Bot size={14} color="white" />
        </div>
      )}

      <div style={{ maxWidth: "78%", display: "flex", flexDirection: "column", gap: 10, alignItems: isUser ? "flex-end" : "flex-start" }}>
        {/* Bubble */}
        {isUser ? (
          <div style={{
            background: "linear-gradient(135deg, #4338ca, #5b21b6)",
            borderRadius: "18px 18px 4px 18px",
            padding: "11px 16px", fontSize: 14, lineHeight: 1.6, color: "#ede9fe",
            boxShadow: "0 4px 24px rgba(79,70,229,0.25)",
          }}>
            {message.content}
          </div>
        ) : (
          <div style={{
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.06)",
            borderRadius: "18px 18px 18px 4px",
            padding: "14px 16px", fontSize: 14, color: "#e2e8f0",
            backdropFilter: "blur(8px)",
          }}>
            {message.content || message.streaming
              ? <>
                  <MD content={message.content} />
                  {message.streaming && <span className="cursor" style={{ display: "inline-block", width: 2, height: 14, background: "#6366f1", borderRadius: 2, marginLeft: 2, verticalAlign: "middle" }} />}
                </>
              : <span style={{ color: "#334155" }}>Thinking…</span>
            }
          </div>
        )}

        {/* Sources */}
        {sources.length > 0 && (
          <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 8 }}>
            {/* Meta row */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingInline: 2 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                {multiFile && <Files size={12} color="#6366f1" />}
                <span style={{ fontSize: 11, color: "#334155" }}>
                  {sources.length} source{sources.length !== 1 ? "s" : ""}
                  {multiFile && <span style={{ color: "#6366f1" }}> · {Object.keys(grouped).length} files</span>}
                  <span style={{ margin: "0 4px" }}>·</span>
                  {message.hops} hop{message.hops !== 1 ? "s" : ""}
                </span>
              </div>
              <CopyBtn text={message.content} />
            </div>

            {/* Cards */}
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {multiFile
                ? Object.entries(grouped).map(([file, chunks]) => (
                    <div key={file}>
                      <p style={{ fontSize: 10, color: "#1e293b", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4, paddingLeft: 2 }}>{file}</p>
                      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                        {chunks.map(s => <SourceCard key={s.globalIndex} source={s} index={s.globalIndex} />)}
                      </div>
                    </div>
                  ))
                : sources.map((s, i) => <SourceCard key={i} source={s} index={i} />)
              }
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
