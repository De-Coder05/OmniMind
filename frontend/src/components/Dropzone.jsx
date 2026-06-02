import { useDropzone } from "react-dropzone";
import { Upload, FileText, ImageIcon, Music, Table2, X } from "lucide-react";

const ACCEPTED = {
  "application/pdf": [".pdf"],
  "image/*": [".png", ".jpg", ".jpeg", ".webp", ".gif"],
  "audio/*": [".mp3", ".wav", ".m4a", ".ogg", ".flac"],
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
};

const META = {
  pdf:  { icon: FileText,  color: "#fb7185" },
  png:  { icon: ImageIcon, color: "#60a5fa" },
  jpg:  { icon: ImageIcon, color: "#60a5fa" },
  jpeg: { icon: ImageIcon, color: "#60a5fa" },
  webp: { icon: ImageIcon, color: "#60a5fa" },
  mp3:  { icon: Music,     color: "#34d399" },
  wav:  { icon: Music,     color: "#34d399" },
  m4a:  { icon: Music,     color: "#34d399" },
  csv:  { icon: Table2,    color: "#fbbf24" },
  xlsx: { icon: Table2,    color: "#fbbf24" },
};

const getMeta = (name) => META[name.split(".").pop().toLowerCase()] || { icon: FileText, color: "#94a3b8" };
const fmtSize = (b) => b < 1024 * 1024 ? `${(b/1024).toFixed(0)} KB` : `${(b/1024/1024).toFixed(1)} MB`;

export default function Dropzone({ files, onChange }) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: ACCEPTED,
    onDrop: (acc) => onChange([...files, ...acc]),
  });

  return (
    <div className="space-y-2">
      <div
        {...getRootProps()}
        style={{
          background: isDragActive ? "rgba(99,102,241,0.07)" : "rgba(255,255,255,0.02)",
          border: `1.5px dashed ${isDragActive ? "#6366f1" : "#2a2a45"}`,
          borderRadius: 12,
          padding: "18px 12px",
          textAlign: "center",
          cursor: "pointer",
          transition: "all 0.15s",
        }}
      >
        <input {...getInputProps()} />
        <div style={{
          width: 36, height: 36, borderRadius: 10, margin: "0 auto 10px",
          background: "rgba(99,102,241,0.1)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Upload size={16} color="#818cf8" />
        </div>
        <p style={{ fontSize: 12, color: "#64748b", lineHeight: 1.5 }}>
          {isDragActive ? "Drop files here" : <><span style={{ color: "#a5b4fc", fontWeight: 500 }}>Click to upload</span> or drag & drop</>}
        </p>
        <p style={{ fontSize: 10, color: "#334155", marginTop: 4 }}>PDF · Image · Audio · CSV · Excel</p>
      </div>

      {files.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {files.map((f, i) => {
            const { icon: Icon, color } = getMeta(f.name);
            return (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 10,
                background: "rgba(255,255,255,0.03)", borderRadius: 10,
                padding: "8px 10px", border: "1px solid #1a1a2e",
              }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                  background: `${color}18`, display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <Icon size={13} color={color} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 11, fontWeight: 500, color: "#cbd5e1", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</p>
                  <p style={{ fontSize: 10, color: "#334155" }}>{fmtSize(f.size)}</p>
                </div>
                <button onClick={() => onChange(files.filter((_, j) => j !== i))}
                  style={{ background: "none", border: "none", cursor: "pointer", padding: 2, borderRadius: 4, opacity: 0.5 }}
                  onMouseEnter={e => e.currentTarget.style.opacity = 1}
                  onMouseLeave={e => e.currentTarget.style.opacity = 0.5}>
                  <X size={12} color="#f87171" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
