import { FileText, Image, Music, Table, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

const MODALITY_STYLE = {
  text: { icon: FileText, color: "text-red-400", bg: "bg-red-950/30", border: "border-red-900/50" },
  image: { icon: Image, color: "text-blue-400", bg: "bg-blue-950/30", border: "border-blue-900/50" },
  audio: { icon: Music, color: "text-green-400", bg: "bg-green-950/30", border: "border-green-900/50" },
  table: { icon: Table, color: "text-yellow-400", bg: "bg-yellow-950/30", border: "border-yellow-900/50" },
};

export default function SourceCard({ source, index }) {
  const [expanded, setExpanded] = useState(false);
  const modality = source.metadata?.modality || "text";
  const style = MODALITY_STYLE[modality] || MODALITY_STYLE.text;
  const Icon = style.icon;

  return (
    <div className={`rounded-lg border p-3 text-xs ${style.bg} ${style.border}`}>
      <div
        className="flex items-center gap-2 cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${style.color}`} />
        <span className="font-medium text-gray-200 truncate">
          {source.metadata?.source || "Unknown"}
        </span>
        {source.metadata?.page && (
          <span className="text-gray-500">p.{source.metadata.page}</span>
        )}
        <span className={`ml-auto px-1.5 py-0.5 rounded text-[10px] font-medium ${style.color} ${style.bg}`}>
          {modality}
        </span>
        <span className="text-gray-500 font-mono">{(source.score * 100).toFixed(0)}%</span>
        {expanded ? (
          <ChevronUp className="w-3.5 h-3.5 text-gray-500" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
        )}
      </div>

      {expanded && (
        <p className="mt-2 text-gray-400 leading-relaxed border-t border-gray-700/50 pt-2">
          {source.text}
        </p>
      )}
    </div>
  );
}
