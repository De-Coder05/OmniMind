import axios from "axios";

const BASE = "http://localhost:8000/api";

export const createSession = () =>
  axios.post(`${BASE}/session/create`).then((r) => r.data.session_id);

export const uploadFiles = (sessionId, files) => {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return axios.post(`${BASE}/session/${sessionId}/upload`, form).then((r) => r.data);
};

export const querySession = (sessionId, query) =>
  axios.post(`${BASE}/query`, { session_id: sessionId, query }).then((r) => r.data);

export const deleteSession = (sessionId) =>
  axios.delete(`${BASE}/session/${sessionId}`);
