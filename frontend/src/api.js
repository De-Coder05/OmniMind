import axios from "axios";

const BASE = "/api";

export const createSession = () =>
  axios.post(`${BASE}/session/create`).then(r => r.data.session_id);

export const uploadFiles = (sessionId, files) => {
  const form = new FormData();
  files.forEach(f => form.append("files", f));
  return axios.post(`${BASE}/session/${sessionId}/upload`, form).then(r => r.data);
};

export const deleteSession = (sessionId) =>
  axios.delete(`${BASE}/session/${sessionId}`);

export async function queryStream(sessionId, query, onToken, onDone) {
  const resp = await fetch(`${BASE}/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, query }),
  });

  if (!resp.ok) throw new Error(`Server error: ${resp.status}`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (raw === "[DONE]") { onDone(null); return; }
      try {
        const parsed = JSON.parse(raw);
        if (parsed.token !== undefined) onToken(parsed.token);
        else if (parsed.sources !== undefined) onDone(parsed);
      } catch {
        onToken(raw);
      }
    }
  }
}
