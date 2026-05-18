import { useEffect, useState } from "react";
import { getProcessStatus, processFile } from "./api";

function App() {
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("");
  const [message, setMessage] = useState("");

  // 작업 시작 후 주기적으로 상태 폴링
  useEffect(() => {
    if (!jobId || !loading) return;
    const timer = setInterval(async () => {
      try {
        const status = await getProcessStatus(jobId);
        setProgress(status.progress ?? 0);
        setStage(status.stage ?? "");
        setMessage(status.message ?? "");
        if (status.status === "completed") {
          setResult(status.result);
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
    }, 800);
    return () => clearInterval(timer);
  }, [jobId, loading]);

  const validateFile = (candidate) => {
    if (!candidate) return "파일을 선택해 주세요.";
    const name = candidate.name.toLowerCase();
    if (!(name.endsWith(".hwp") || name.endsWith(".hwpx"))) {
      return "hwp, hwpx 파일만 업로드할 수 있습니다.";
    }
    return "";
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setProgress(0);
    setStage("");
    setMessage("");

    const validationError = validateFile(file);
    if (validationError) return setError(validationError);

    try {
      setLoading(true);
      const data = await processFile(file);
      setJobId(data.job_id);
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
    if (validationError) return setError(validationError);
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
    <main className="container">
      <h1>HWP/HWPX OCR + 요약</h1>

      <form onSubmit={onSubmit} className="panel">
        <div
          className={`dropzone ${dragOver ? "dragOver" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          <p>여기에 파일을 드래그 앤 드롭하거나 아래에서 선택하세요.</p>
          <input type="file" accept=".hwp,.hwpx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <p className="selectedFile">{file ? `선택 파일: ${file.name}` : "선택된 파일 없음"}</p>
        </div>
        <button type="submit" disabled={loading}>
          {loading ? "처리 중..." : "업로드 및 처리"}
        </button>
      </form>

      {loading && (
        <section className="panel">
          <h2>진행 상태</h2>
          <p><strong>job_id:</strong> {jobId}</p>
          <p><strong>progress:</strong> {progress}%</p>
          <p><strong>stage:</strong> {stage}</p>
          <p>{message}</p>
          <progress value={progress} max="100" style={{ width: "100%" }} />
        </section>
      )}

      {error && <p className="error">{error}</p>}

      {result && (
        <section className="panel">
          <h2>결과</h2>
          <p><strong>파일명:</strong> {result.filename}</p>
          <p><strong>카테고리:</strong> {result.category}</p>
          <div className="actions">
            <button
              type="button"
              onClick={() => downloadText("summary.txt", `filename: ${result.filename}\n\nsummary:\n${result.summary}\n`)}
            >
              요약 파일 다운로드
            </button>
            <button
              type="button"
              onClick={() => downloadText("category.txt", `filename: ${result.filename}\ncategory: ${result.category}\n`)}
            >
              분류 파일 다운로드
            </button>
          </div>
          <h3>요약</h3>
          <pre>{result.summary}</pre>
          <h3>Direct Text</h3>
          <pre>{result.raw_text}</pre>
          <h3>OCR Text</h3>
          <pre>{result.ocr_text}</pre>
          <h3>Merged Text</h3>
          <pre>{result.merged_text}</pre>
        </section>
      )}

      {/* 검색 기능은 현재 미사용 */}
    </main>
  );
}

export default App;
