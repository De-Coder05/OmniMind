import { useDropzone } from "react-dropzone";
import { Upload, FileText, Image, Music, Table } from "lucide-react";

const ACCEPTED = {
  "application/pdf": [".pdf"],
  "image/*": [".png", ".jpg", ".jpeg", ".webp", ".gif"],
  "audio/*": [".mp3", ".wav", ".m4a", ".ogg", ".flac"],
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
};

const iconFor = (name) => {
  const ext = name.split(".").pop().toLowerCase();
  if (ext === "pdf") return <FileText className="w-4 h-4 text-red-400" />;
  if (["png", "jpg", "jpeg", "webp", "gif"].includes(ext))
    return <Image className="w-4 h-4 text-blue-400" />;
  if (["mp3", "wav", "m4a", "ogg", "flac"].includes(ext))
    return <Music className="w-4 h-4 text-green-400" />;
  return <Table className="w-4 h-4 text-yellow-400" />;
};

export default function Dropzone({ files, onChange }) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: ACCEPTED,
    onDrop: (accepted) => onChange([...files, ...accepted]),
  });

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
          ${isDragActive ? "border-indigo-500 bg-indigo-950/30" : "border-gray-700 hover:border-gray-500 bg-gray-900/40"}`}
      >
        <input {...getInputProps()} />
        <Upload className="w-8 h-8 mx-auto mb-3 text-gray-500" />
        <p className="text-sm text-gray-400">
          {isDragActive ? "Drop files here..." : "Drag & drop or click to upload"}
        </p>
        <p className="text-xs text-gray-600 mt-1">PDF · Images · Audio · CSV / Excel</p>
      </div>

      {files.length > 0 && (
        <ul className="space-y-1">
          {files.map((f, i) => (
            <li
              key={i}
              className="flex items-center gap-2 text-sm text-gray-300 bg-gray-800/50 rounded-lg px-3 py-2"
            >
              {iconFor(f.name)}
              <span className="truncate">{f.name}</span>
              <span className="ml-auto text-xs text-gray-500">
                {(f.size / 1024).toFixed(0)} KB
              </span>
              <button
                onClick={() => onChange(files.filter((_, j) => j !== i))}
                className="text-gray-600 hover:text-red-400 ml-1"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
