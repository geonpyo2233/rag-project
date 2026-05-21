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

// 처리 이력 조회 API (PostgreSQL)
// 최신순으로 이력 목록을 가져옵니다.
export async function getHistory(limit = 100) {
  const { data } = await api.get('/api/history', { params: { limit } });
  return data;
}

// 처리 이력 검색 API (PostgreSQL)
// 파일명/요약/카테고리를 기준으로 부분 일치 검색합니다.
export async function searchHistory(query, limit = 100) {
  const { data } = await api.get('/api/history/search', { params: { q: query, limit } });
  return data;
}

