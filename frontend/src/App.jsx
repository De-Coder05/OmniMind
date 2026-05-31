import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Trash2, Zap } from "lucide-react";
import Dropzone from "./components/Dropzone";
import ChatMessage from "./components/ChatMessage";
import { createSession, uploadFiles, querySession, deleteSession } from "./api";

export default function App() {
  const [sessionId, setSessionId] = useState(null);
  const [files, setFiles] = useState([]);
  const [indexing, setIndexing] = useState(false);
  const [indexResult, setIndexResult] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

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
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    try {
      const data = await querySession(sessionId, q);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources,
          hops: data.hops,
        },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${e.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (sessionId) await deleteSession(sessionId).catch(() => {});
    setSessionId(null);
    setFiles([]);
    setIndexResult(null);
    setMessages([]);
    setInput("");
  };

  const ready = !!sessionId && !indexing;

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      <aside className="w-80 flex-shrink-0 border-r border-gray-800 flex flex-col p-4 gap-4">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center">
            <Zap className="w-4 h-4" />
          </div>
          <h1 className="font-semibold text-lg">OmniMind</h1>
          <span className="text-xs text-gray-500 ml-auto">Multimodal RAG</span>
        </div>

        <div className="border-t border-gray-800 pt-4 space-y-3 flex-1">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Documents</p>
          <Dropzone files={files} onChange={setFiles} />

          <button
            onClick={handleIndex}
            disabled={!files.length || indexing}
            className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40
              disabled:cursor-not-allowed text-sm font-medium transition-colors flex items-center justify-center gap-2"
          >
            {indexing ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Indexing…</>
            ) : (
              "Index Documents"
            )}
          </button>

          {indexResult && !indexResult.error && (
            <div className="rounded-lg bg-gray-800/50 p-3 text-xs space-y-1">
              {indexResult.files.map((f, i) => (
                <div key={i} className="flex justify-between text-gray-400">
                  <span className="truncate">{f.file}</span>
                  <span className="text-indigo-400 flex-shrink-0 ml-2">{f.chunks_indexed} chunks</span>
                </div>
              ))}
            </div>
          )}

          {indexResult?.error && (
            <p className="text-xs text-red-400 bg-red-950/30 rounded-lg p-2">
              {indexResult.error}
            </p>
          )}
        </div>

        {sessionId && (
          <button
            onClick={handleReset}
            className="flex items-center gap-2 text-xs text-gray-500 hover:text-red-400 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear session
          </button>
        )}
      </aside>

      <main className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center text-gray-600 select-none">
              <Zap className="w-12 h-12 mb-4 text-gray-800" />
              <p className="text-lg font-medium text-gray-500">Ask anything about your documents</p>
              <p className="text-sm mt-1">Upload PDFs, images, audio or tables — then query across all of them</p>
            </div>
          )}
          {messages.map((m, i) => (
            <ChatMessage key={i} message={m} />
          ))}
          {loading && (
            <div className="flex gap-3">
              <div className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center">
                <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
              </div>
              <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-gray-400">
                Searching and reasoning…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-gray-800 p-4">
          <div className="flex gap-3 items-end">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleQuery();
                }
              }}
              placeholder={ready ? "Ask a question about your documents…" : "Index documents first to start querying"}
              disabled={!ready || loading}
              rows={1}
              className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm
                resize-none focus:outline-none focus:border-indigo-500 disabled:opacity-40
                placeholder-gray-600 transition-colors leading-relaxed"
              style={{ minHeight: "48px", maxHeight: "160px" }}
            />
            <button
              onClick={handleQuery}
              disabled={!ready || !input.trim() || loading}
              className="h-12 w-12 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40
                disabled:cursor-not-allowed flex items-center justify-center transition-colors flex-shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <p className="text-xs text-gray-700 mt-2 text-center">
            OmniMind uses local inference — your documents never leave your machine
          </p>
        </div>
      </main>
    </div>
  );
}
