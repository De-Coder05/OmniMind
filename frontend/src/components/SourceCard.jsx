import { FileText, ImageIcon, Music, Table2, ChevronDown } from "lucide-react";
import { useState } from "react";

const M = {
  text:  { icon: FileText,  color: "#fb7185", bg: "rgba(251,113,133,0.1)"  },
  image: { icon: ImageIcon, color: "#60a5fa", bg: "rgba(96,165,250,0.1)"   },
  audio: { icon: Music,     color: "#34d399", bg: "rgba(52,211,153,0.1)"   },
  table: { icon: Table2,    color: "#fbbf24", bg: "rgba(251,191,36,0.1)"   },
};

export default function SourceCard({ source, index }) {
  const [open, setOpen] = useState(false);
  const m = M[source.metadata?.modality] || M.text;
  const Icon = m.icon;
  const name = source.metadata?.source || "Unknown";
  const short = name.length > 28 ? name.slice(0, 26) + "…" : name;

  return (
    <div style={{
      borderRadius: 10, overflow: "hidden",
      background: "rgba(255,255,255,0.02)",
      border: `1px solid ${open ? "#2e2e50" : "#1a1a2e"}`,
      transition: "border-color 0.15s",
    }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 8,
          padding: "8px 10px", background: "none", border: "none",
          cursor: "pointer", textAlign: "left",
        }}
        onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.02)"}
        onMouseLeave={e => e.currentTarget.style.background = "none"}
      >
        {/* rank */}
        <span style={{
          minWidth: 20, height: 20, borderRadius: 6, fontSize: 10, fontWeight: 700,
          background: "rgba(99,102,241,0.15)", color: "#818cf8",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>{index + 1}</span>

        {/* modality icon */}
        <span style={{
          width: 20, height: 20, borderRadius: 5, background: m.bg,
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          <Icon size={11} color={m.color} />
        </span>

        {/* name + page */}
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={{ fontSize: 11, fontWeight: 500, color: "#cbd5e1" }}>{short}</span>
          {source.metadata?.page && (
            <span style={{ fontSize: 10, color: "#334155", marginLeft: 6 }}>p.{source.metadata.page}</span>
          )}
        </span>

        {/* modality badge */}
        <span style={{
          fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em",
          padding: "2px 6px", borderRadius: 4, background: m.bg, color: m.color, flexShrink: 0,
        }}>{source.metadata?.modality || "text"}</span>

        <ChevronDown size={12} color="#334155" style={{
          flexShrink: 0, transition: "transform 0.2s",
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
        }} />
      </button>

      {open && (
        <div style={{
          padding: "10px 12px 12px", fontSize: 11, lineHeight: 1.7,
          color: "#64748b", borderTop: "1px solid #1a1a2e",
        }}>
          {source.text}
        </div>
      )}
    </div>
  );
}
