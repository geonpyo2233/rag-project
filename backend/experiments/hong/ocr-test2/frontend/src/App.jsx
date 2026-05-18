import { useEffect, useState } from "react";
import { getProcessStatus, processFile } from "./api";

const TEXT_TABS = [
  { key: "summary", label: "요약" },
  { key: "raw_text", label: "Direct Text" },
  { key: "ocr_text", label: "OCR Text" },
  { key: "merged_text", label: "Merged Text" },
];

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
  const [activeTab, setActiveTab] = useState("summary");

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
    }, 900);

    return () => clearInterval(timer);
  }, [jobId, loading]);

  const validateFile = (candidate) => {
    if (!candidate) return "파일을 선택해 주세요.";
    const name = candidate.name.toLowerCase();
    if (!(name.endsWith(".hwp") || name.endsWith(".hwpx"))) {
      return "hwp 또는 hwpx 파일만 업로드할 수 있습니다.";
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
    setActiveTab("summary");

    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }

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

  const getTabContent = () => {
    if (!result) return "";
    return result[activeTab] || "";
  };

  return (
    <div className="page">
      <aside className="sidebar">
        <div className="brand">
          <span className="brandMark">OCR</span>
          <div>
            <h1>OCR Test2</h1>
            <p>HWP/HWPX 문서 처리 파이프라인</p>
          </div>
        </div>
        <div className="sidebarHint">
          <p>1) 파일 업로드</p>
          <p>2) 객체 OCR 처리</p>
          <p>3) 결과 확인</p>
        </div>
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
                accept=".hwp,.hwpx"
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
            <span className="jobId">{jobId ? `job_id: ${jobId}` : "job_id 없음"}</span>
          </div>

          <div className="statusGrid">
            <div className="metric">
              <span>진행률</span>
              <strong>{progress}%</strong>
            </div>
            <div className="metric">
              <span>단계</span>
              <strong>{stage || "-"}</strong>
            </div>
            <div className="metric">
              <span>메시지</span>
              <strong>{message || "-"}</strong>
            </div>
          </div>
          <progress value={progress} max="100" />
        </section>

        {error && <p className="error">{error}</p>}

        {result && (
          <section className="card resultCard">
            <div className="cardHeader">
              <h2>처리 결과</h2>
              <div className="actions">
                <button
                  type="button"
                  onClick={() =>
                    downloadText(
                      "summary.txt",
                      `filename: ${result.filename}\n\nsummary:\n${result.summary}\n`,
                    )
                  }
                >
                  요약 다운로드
                </button>
                <button
                  type="button"
                  onClick={() =>
                    downloadText(
                      "category.txt",
                      `filename: ${result.filename}\ncategory: ${result.category}\n`,
                    )
                  }
                >
                  분류 다운로드
                </button>
              </div>
            </div>

            <div className="metaRow">
              <p>
                <b>파일명:</b> {result.filename}
              </p>
              <p>
                <b>카테고리:</b> {result.category}
              </p>
            </div>

            <div className="tabRow">
              {TEXT_TABS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  className={`tabBtn ${activeTab === tab.key ? "active" : ""}`}
                  onClick={() => setActiveTab(tab.key)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <pre>{getTabContent()}</pre>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
