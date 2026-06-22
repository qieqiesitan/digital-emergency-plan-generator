import axios from "axios";

const API_BASE = "/api/v1";

export async function uploadFile(file: File): Promise<string> {
  const token = localStorage.getItem("access_token");
  const formData = new FormData();
  formData.append("file", file);
  const res = await axios.post<{ code: number; data: { url: string } }>(`${API_BASE}/upload`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  return res.data.data.url;
}
