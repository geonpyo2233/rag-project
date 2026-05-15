import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000"
});

// 문서 처리 시작(job_id 반환)
export async function processFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/api/process/start", formData, {
    headers: {
      "Content-Type": "multipart/form-data"
    }
  });
  return data;
}

// 작업 진행 상태 조회
export async function getProcessStatus(jobId) {
  const { data } = await api.get(`/api/process/${jobId}`);
  return data;
}

// 저장된 문서 유사도 검색
export async function searchDocuments(query, limit = 5) {
  const { data } = await api.post("/api/search", { query, limit });
  return data;
}
