import { useEffect, useMemo, useState } from "react";
import { getProcessStatus, processFile } from "./api";

const HISTORY_STORAGE_KEY = "rag_history_items_v1";
const HISTORY_SELECTED_KEY = "rag_history_selected_v1";

function App() {
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [jobId, setJobId] = useState("");

  const [historyItems, setHistoryItems] = useState([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState("");

  const selectedItem = useMemo(
    () => historyItems.find((item) => item.jobId === selectedHistoryId) || null,
    [historyItems, selectedHistoryId],
  );
  const selectedResult = selectedItem?.result || null;

  useEffect(() => {
    try {
      const savedItems = localStorage.getItem(HISTORY_STORAGE_KEY);
      const savedSelected = localStorage.getItem(HISTORY_SELECTED_KEY);
      if (savedItems) {
        const parsed = JSON.parse(savedItems);
        if (Array.isArray(parsed)) {
          setHistoryItems(parsed);
          if (savedSelected && parsed.some((item) => item.jobId === savedSelected)) {
            setSelectedHistoryId(savedSelected);
          } else if (parsed[0]?.jobId) {
            setSelectedHistoryId(parsed[0].jobId);
          }
        }
      }
    } catch {
      // localStorage parsing fallback
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(historyItems));
  }, [historyItems]);

  useEffect(() => {
    if (selectedHistoryId) {
      localStorage.setItem(HISTORY_SELECTED_KEY, selectedHistoryId);
    }
  }, [selectedHistoryId]);

  useEffect(() => {
    if (!jobId || !loading) return;

    const timer = setInterval(async () => {
      try {
        const status = await getProcessStatus(jobId);

        setHistoryItems((prev) =>
          prev.map((item) =>
            item.jobId === jobId
              ? {
                  ...item,
                  status: status.status ?? item.status,
                  progress: status.progress ?? item.progress,
                  stage: status.stage ?? item.stage,
                  message: status.message ?? item.message,
                  result: status.result ?? item.result,
                  updatedAt: new Date().toISOString(),
                }
              : item,
          ),
        );

        if (status.status === "completed") {
          setLoading(false);
          clearInterval(timer);
        } else if (status.status === "failed") {
          setError(status.message || "처리에 실패했습니다.");
          setLoading(false);
          clearInterval(timer);
        }
      } catch {
        setError("진행 상태 조회 중 오류가 발생했습니다.");
        setLoading(false);
        clearInterval(timer);
      }
    }, 900);

    return () => clearInterval(timer);
  }, [jobId, loading]);

  const validateFile = (candidate) => {
    if (!candidate) return "파일을 선택해 주세요.";
    const name = candidate.name.toLowerCase();
    if (
      !(
        name.endsWith(".hwp") ||
        name.endsWith(".hwpx") ||
        name.endsWith(".pdf") ||
        name.endsWith(".docx") ||
        name.endsWith(".ppt") ||
        name.endsWith(".pptx")
      )
    ) {
      return "hwp, hwpx, pdf, docx, ppt, pptx 파일만 업로드할 수 있습니다.";
    }
    return "";
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    try {
      setLoading(true);
      const data = await processFile(file);
      setJobId(data.job_id);

      const newHistory = {
        jobId: data.job_id,
        filename: file.name,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        status: "queued",
        progress: 0,
        stage: "queued",
        message: "작업 대기 중",
        result: null,
      };

      setHistoryItems((prev) => [newHistory, ...prev]);
      setSelectedHistoryId(data.job_id);
    } catch (err) {
      setError(err?.response?.data?.detail || "처리 시작 중 오류가 발생했습니다.");
      setLoading(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    setError("");

    const dropped = e.dataTransfer.files?.[0];
    const validationError = validateFile(dropped);
    if (validationError) {
      setError(validationError);
      return;
    }
    setFile(dropped);
  };

  const downloadText = (filename, content) => {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page">
      <aside className="sidebar">
        <div className="brand">
          <span className="brandMark">OCR</span>
          <div>
            <h1>AI기반</h1>
            <h1>문서 요약 및 카테고리 분류</h1>
            <h1>RAG 시스템</h1>
          </div>
        </div>

        <div className="sidebarHint">
          <p>1) 파일 업로드</p>
          <p>2) OCR</p>
          <p>3) 결과 확인</p>
        </div>

        <section className="historyPanel">
          <h3>처리 이력</h3>
          <div className="historyList">
            {historyItems.length === 0 && (
              <p className="historyEmpty">아직 처리 이력이 없습니다.</p>
            )}
            {historyItems.map((item) => (
              <button
                type="button"
                key={item.jobId}
                className={`historyItem ${selectedHistoryId === item.jobId ? "active" : ""}`}
                onClick={() => setSelectedHistoryId(item.jobId)}
                title={item.filename}
              >
                <strong>{item.filename}</strong>
              </button>
            ))}
          </div>
        </section>
      </aside>

      <main className="content">
        <section className="card uploadCard">
          <div className="cardHeader">
            <h2>문서 업로드</h2>
            <span className={`statusChip ${loading ? "loading" : "idle"}`}>
              {loading ? "처리 중" : "대기"}
            </span>
          </div>

          <form onSubmit={onSubmit}>
            <div
              className={`dropzone ${dragOver ? "dragOver" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
            >
              <p>파일을 끌어놓거나 아래에서 선택해 주세요.</p>
              <input
                type="file"
                accept=".hwp,.hwpx,.pdf,.docx,.ppt,.pptx"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <p className="selectedFile">{file ? file.name : "선택된 파일 없음"}</p>
            </div>

            <div className="buttonRow">
              <button type="submit" className="primaryBtn" disabled={loading}>
                {loading ? "처리 중..." : "업로드 및 처리"}
              </button>
            </div>
          </form>
        </section>

        <section className="card statusCard">
          <div className="cardHeader">
            <h2>진행 상태</h2>
            <span className="jobId">
              {selectedItem?.jobId ? `job_id: ${selectedItem.jobId}` : "job_id 없음"}
            </span>
          </div>

          <div className="statusGrid">
            <div className="metric">
              <span>진행률</span>
              <strong>{selectedItem?.progress ?? 0}%</strong>
            </div>
            <div className="metric">
              <span>단계</span>
              <strong>{selectedItem?.stage || "-"}</strong>
            </div>
            <div className="metric">
              <span>메시지</span>
              <strong>{selectedItem?.message || "-"}</strong>
            </div>
          </div>
          <progress value={selectedItem?.progress ?? 0} max="100" />
        </section>

        {error && <p className="error">{error}</p>}

        {selectedItem && (
          <section className="card resultCard">
            <div className="cardHeader">
              <h2>처리 결과</h2>
              <div className="actions">
                <button
                  type="button"
                  disabled={!selectedResult?.summary}
                  onClick={() =>
                    downloadText(
                      "summary.txt",
                      `filename: ${selectedResult?.filename || selectedItem.filename}\n\nsummary:\n${selectedResult?.summary || ""}\n`,
                    )
                  }
                >
                  요약 다운로드
                </button>
                <button
                  type="button"
                  disabled={!selectedResult}
                  onClick={() =>
                    downloadText(
                      "category.txt",
                      `filename: ${selectedResult?.filename || selectedItem.filename}\nmain_category: ${selectedResult?.main_category || selectedResult?.category || "기타"}\nsub_category: ${selectedResult?.sub_category || "미상"}\n`,
                    )
                  }
                >
                  분류 다운로드
                </button>
              </div>
            </div>

            <div className="metaRow">
              <p>
                <b>파일명:</b> {selectedResult?.filename || selectedItem.filename}
              </p>
              <p>
                <b>메인 카테고리:</b> {selectedResult?.main_category || selectedResult?.category || "분류 대기"}
              </p>
              <p>
                <b>서브 카테고리:</b> {selectedResult?.sub_category || "미상"}
              </p>
              <p>
                <b>진행 상태:</b> {selectedItem.status}
              </p>
            </div>

            <pre>{selectedResult?.summary || "요약 결과가 아직 없습니다."}</pre>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
