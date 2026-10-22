import { useState, useEffect, useCallback } from "react";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

function App() {
  const emptyComplaint = {
    customer_name: "",
    product_name: "",
    product_strength: "",
    batch_number: "",
    manufacturing_date: "",
    expiry_date: "",
    affected_quantity: "",
    complaint: "",
    severity: "",
    severity_reason: "",
    risk_level: "",
    recommended_action: ""
  };

  const [files, setFiles] = useState([]);
  const [statusNotice, setStatusNotice] = useState({ text: "", type: "" });
  const [loading, setLoading] = useState(false);
  const [selectedPDF, setSelectedPDF] = useState("");
  const [showChat, setShowChat] = useState(false);
  const [chatMessage, setChatMessage] = useState("");
  const [chatFile, setChatFile] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const [complaintData, setComplaintData] = useState(emptyComplaint);
  const [registeredCases, setRegisteredCases] = useState([]);
  const [batchSignals, setBatchSignals] = useState([]);
  const [caseSummary, setCaseSummary] = useState({
    total: 0,
    critical: 0,
    pending: 0,
    resolved: 0
  });
  const [registerError, setRegisterError] = useState("");
  const [registerLoading, setRegisterLoading] = useState(false);

  const notify = (text, type = "info") => {
    setStatusNotice({ text, type });
    if (type !== "error") {
      setTimeout(() => {
        setStatusNotice(prev => (prev.text === text ? { text: "", type: "" } : prev));
      }, 5000);
    }
  };

  const saveComplaintData = (data) => {
    const safeData = { ...emptyComplaint, ...(data || {}) };
    setComplaintData(safeData);
  };

  const loadFiles = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/files`);
      if (!response.ok) throw new Error("Could not load uploaded documents");
      const data = await response.json();
      setFiles(data.files || []);
    } catch (error) {
      console.error("File loading error:", error);
    }
  }, []);

  const loadRegister = useCallback(async () => {
    try {
      setRegisterLoading(true);
      const [casesResponse, signalsResponse, summaryResponse] = await Promise.all([
        fetch(`${API_BASE}/complaints?limit=50`),
        fetch(`${API_BASE}/analytics/batch-signals?days=30&min_reports=2`),
        fetch(`${API_BASE}/analytics/summary`)
      ]);
      if (!casesResponse.ok || !signalsResponse.ok || !summaryResponse.ok) {
        throw new Error("Complaint register service unavailable");
      }
      const [casesData, signalsData, summaryData] = await Promise.all([
        casesResponse.json(),
        signalsResponse.json(),
        summaryResponse.json()
      ]);
      setRegisteredCases(casesData.cases || []);
      setBatchSignals(signalsData.signals || []);
      setCaseSummary({
        total: Number(summaryData.total || 0),
        critical: Number(summaryData.critical || 0),
        pending: Number(summaryData.pending || 0),
        resolved: Number(summaryData.resolved || 0)
      });
      setRegisterError("");
    } catch (error) {
      console.error("Register loading error:", error);
      setRegisterError("Live complaint register offline. Ensure FastAPI backend is running.");
    } finally {
      setRegisterLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFiles();
    loadRegister();
  }, [loadFiles, loadRegister]);

  const analyzeComplaint = async (filename) => {
    try {
      setLoading(true);
      notify(`Reading ${filename}...`, "info");

      const extractResponse = await fetch(`${API_BASE}/extract/${encodeURIComponent(filename)}`);
      if (!extractResponse.ok) {
        const err = await extractResponse.json().catch(() => ({}));
        throw new Error(err.error || "Failed to extract text from PDF");
      }

      const extracted = await extractResponse.json();
      if (!extracted.text || extracted.text.trim().length === 0) {
        throw new Error("PDF contains no extractable text");
      }

      notify("Analyzing complaint document with AI...", "info");
      const aiResponse = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: extracted.text, session_id: "demo-user" })
      });

      if (!aiResponse.ok) {
        throw new Error("Complaint triage engine encountered an error");
      }

      const aiData = await aiResponse.json();
      saveComplaintData(aiData.complaint);
      await loadRegister();
      notify(`Analysis complete for ${filename}`, "success");
    } catch (error) {
      console.error("AI Error:", error);
      notify(error.message || "Failed to analyze complaint", "error");
    } finally {
      setLoading(false);
    }
  };

  const resetSession = async () => {
    try {
      await fetch(`${API_BASE}/chat/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: "demo-user" })
      });
    } catch (e) {
      console.warn("Reset error:", e);
    }
    setShowChat(false);
    setChatMessage("");
    setChatFile(null);
    setChatHistory([]);
    setComplaintData(emptyComplaint);
    notify("Conversation reset.", "info");
  };

  const sendComplaint = async () => {
    if (!chatMessage.trim() && !chatFile) {
      notify("Please type a message or select a PDF to upload.", "error");
      return;
    }

    try {
      setLoading(true);

      if (chatFile) {
        // Validation
        if (!chatFile.name.toLowerCase().endsWith(".pdf")) {
          notify("Only PDF files are supported.", "error");
          setLoading(false);
          return;
        }
        if (chatFile.size > 10 * 1024 * 1024) {
          notify("PDF file size must not exceed 10MB.", "error");
          setLoading(false);
          return;
        }

        notify("Uploading PDF securely...", "info");
        const formData = new FormData();
        formData.append("file", chatFile);

        const uploadResponse = await fetch(`${API_BASE}/upload`, {
          method: "POST",
          body: formData
        });

        if (!uploadResponse.ok) {
          const err = await uploadResponse.json().catch(() => ({}));
          throw new Error(err.error || "File upload failed");
        }

        const uploadData = await uploadResponse.json();
        const filename = uploadData.filename;
        await loadFiles();

        notify(`Extracting text from ${filename}...`, "info");
        const extractResponse = await fetch(`${API_BASE}/extract/${encodeURIComponent(filename)}`);
        if (!extractResponse.ok) {
          throw new Error("Failed to extract text from uploaded PDF");
        }
        const extractedData = await extractResponse.json();

        notify("Triaging extracted complaint...", "info");
        const aiResponse = await fetch(`${API_BASE}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: extractedData.text, session_id: "demo-user" })
        });

        if (!aiResponse.ok) {
          throw new Error("Complaint triage engine failed");
        }

        const aiData = await aiResponse.json();
        saveComplaintData(aiData.complaint);
        await loadRegister();

        setChatHistory(prev => [
          ...prev,
          { role: "user", content: `Uploaded PDF: ${chatFile.name}` },
          { role: "assistant", content: aiData.reply || "Extracted and recorded complaint case." }
        ]);

        setChatFile(null);
        notify("PDF complaint processed successfully.", "success");
      } else if (chatMessage.trim()) {
        const userText = chatMessage.trim();
        setChatMessage("");

        const response = await fetch(`${API_BASE}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: userText, session_id: "demo-user" })
        });

        if (!response.ok) {
          throw new Error("Chat request failed");
        }

        const data = await response.json();
        saveComplaintData(data.complaint);
        await loadRegister();

        setChatHistory(prev => [
          ...prev,
          { role: "user", content: userText },
          { role: "assistant", content: data.reply }
        ]);
      }
    } catch (error) {
      console.error("Chat Error:", error);
      notify(error.message || "Unable to process request.", "error");
    } finally {
      setLoading(false);
    }
  };

  const openSavedCase = async (complaintId) => {
    try {
      const response = await fetch(`${API_BASE}/complaints/${encodeURIComponent(complaintId)}`);
      if (!response.ok) throw new Error("Could not open saved complaint");
      const data = await response.json();
      saveComplaintData(data.case);
      setShowChat(false);
      notify(`Loaded case ${complaintId}`, "info");
    } catch (error) {
      setRegisterError("Could not load case details.");
    }
  };

  return (
    <div className="container">
      <div className="header">
        <h1>🛡️ PharmaGuard AI</h1>
        <p>AI-Powered Pharmaceutical Complaint Intelligence & Pharmacovigilance Platform</p>
      </div>

      {statusNotice.text && (
        <div
          role="status"
          style={{
            padding: "12px 18px",
            marginBottom: "20px",
            borderRadius: "10px",
            fontWeight: 600,
            textAlign: "center",
            background:
              statusNotice.type === "error"
                ? "#fee2e2"
                : statusNotice.type === "success"
                ? "#dcfce7"
                : "#e0f2fe",
            color:
              statusNotice.type === "error"
                ? "#991b1b"
                : statusNotice.type === "success"
                ? "#166534"
                : "#0369a1",
            border: `1px solid ${
              statusNotice.type === "error"
                ? "#fca5a5"
                : statusNotice.type === "success"
                ? "#86efac"
                : "#7dd3fc"
            }`
          }}
        >
          {statusNotice.text}
        </div>
      )}

      <div className="dashboard-cards">
        <div className="dashboard-card">
          <h3>Total Complaints</h3>
          <p>{caseSummary.total}</p>
        </div>
        <div className="dashboard-card">
          <h3>Critical Issues</h3>
          <p style={{ color: "#dc2626" }}>{caseSummary.critical}</p>
        </div>
        <div className="dashboard-card">
          <h3>Under Investigation</h3>
          <p style={{ color: "#d97706" }}>{caseSummary.pending}</p>
        </div>
        <div className="dashboard-card">
          <h3>Resolved</h3>
          <p style={{ color: "#16a34a" }}>{caseSummary.resolved}</p>
        </div>
      </div>

      <div className="card">
        {!showChat ? (
          <>
            <h2>Intelligent Complaint Intake</h2>
            <p>
              Report a pharmaceutical issue, packaging defect, or adverse reaction through conversational intake or PDF upload.
            </p>
            <button className="primary-btn" onClick={() => setShowChat(true)}>
              ➕ Create / Triage Complaint
            </button>
          </>
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2>New Complaint Case</h2>
              <button
                type="button"
                className="secondary-btn"
                style={{ padding: "6px 14px", fontSize: "13px" }}
                onClick={resetSession}
              >
                🔄 Reset Chat
              </button>
            </div>

            {chatHistory.length > 0 && (
              <div className="chat-window">
                {chatHistory.map((msg, index) => (
                  <div
                    key={index}
                    className={msg.role === "user" ? "user-message" : "ai-message"}
                  >
                    <strong>{msg.role === "user" ? "User / Reporter" : "PharmaGuard AI"}</strong>
                    <p style={{ whiteSpace: "pre-wrap" }}>{msg.content}</p>
                  </div>
                ))}
              </div>
            )}

            <textarea
              rows="3"
              placeholder="Describe the complaint (e.g. 'City Pharmacy reported contaminated blister packs for Amoxicillin 500mg, batch ABC-102')..."
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              disabled={loading}
            />

            <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap", margin: "10px 0" }}>
              <label className="upload-btn">
                📎 Attach Complaint PDF
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => {
                    const f = e.target.files[0];
                    if (f) setChatFile(f);
                  }}
                />
              </label>
              {chatFile && (
                <span style={{ fontSize: "14px", color: "#2563eb", fontWeight: 500 }}>
                  📄 {chatFile.name} ({(chatFile.size / 1024).toFixed(1)} KB)
                  <button
                    type="button"
                    style={{ background: "transparent", color: "#ef4444", border: "none", cursor: "pointer", marginLeft: "6px" }}
                    onClick={() => setChatFile(null)}
                  >
                    ✕
                  </button>
                </span>
              )}
            </div>

            <button className="primary-btn" onClick={sendComplaint} disabled={loading}>
              {loading ? "Processing..." : "Submit to Intake Engine"}
            </button>

            <button className="secondary-btn" onClick={resetSession} disabled={loading}>
              Close
            </button>
          </>
        )}
      </div>

      <div className="card">
        <h2>📁 Uploaded Source Documents</h2>
        <ul>
          {files.length === 0 ? (
            <p style={{ color: "#6b7280" }}>No complaint PDFs uploaded yet.</p>
          ) : (
            files.map((item) => (
              <li
                key={item}
                onClick={async () => {
                  setSelectedPDF(item);
                  window.open(`${API_BASE}/files/${encodeURIComponent(item)}`, "_blank");
                  await analyzeComplaint(item);
                }}
              >
                📄 <strong>{item}</strong>
                <span style={{ float: "right", fontSize: "13px", color: "#2563eb" }}>Click to inspect & re-triage →</span>
              </li>
            ))
          )}
        </ul>
        {selectedPDF && (
          <p style={{ fontSize: "13px", color: "#6b7280", marginTop: "8px" }}>
            Active PDF: <strong>{selectedPDF}</strong>
          </p>
        )}
      </div>

      <div className="card">
        <h2>🗂️ Persisted Complaint Register</h2>
        <p style={{ color: "#6b7280", margin: "4px 0 16px" }}>
          Case records are maintained in the local SQLite audit store and persist across sessions.
        </p>
        {registerLoading && <p className="loading">Refreshing complaint queue…</p>}
        {registerError && <p role="alert" style={{ color: "#dc2626" }}>{registerError}</p>}

        {batchSignals.length > 0 && (
          <div className="batch-signal-panel" style={{ background: "#fffbeb", border: "1px solid #fde68a", padding: "16px", borderRadius: "10px", marginBottom: "20px", textAlign: "left" }}>
            <h3 style={{ color: "#b45309", marginTop: 0 }}>⚠️ Potential Repeat Batch Signals (30-Day Window)</h3>
            <p style={{ fontSize: "14px", color: "#92400e" }}>
              Signals highlight repeat reports requiring qualified quality investigation. They do not confirm a defect or causality.
            </p>
            <ul style={{ margin: "10px 0 0" }}>
              {batchSignals.map((signal) => (
                <li key={`${signal.product_key}-${signal.batch_key}`} style={{ background: "white" }}>
                  <strong>{signal.product_name}</strong> · Batch <strong>{signal.batch_number}</strong>:
                  {" "}{signal.report_count} incident reports ({signal.critical_count} critical).
                </li>
              ))}
            </ul>
          </div>
        )}

        {registeredCases.length === 0 ? (
          <p style={{ color: "#6b7280" }}>No registered cases found in the audit store.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", padding: "12px", background: "#f1f5f9" }}>Case ID</th>
                  <th style={{ textAlign: "left", padding: "12px", background: "#f1f5f9" }}>Product</th>
                  <th style={{ textAlign: "left", padding: "12px", background: "#f1f5f9" }}>Batch</th>
                  <th style={{ textAlign: "left", padding: "12px", background: "#f1f5f9" }}>Severity</th>
                  <th style={{ textAlign: "left", padding: "12px", background: "#f1f5f9" }}>Status</th>
                  <th style={{ textAlign: "left", padding: "12px", background: "#f1f5f9" }}>Last Updated (UTC)</th>
                </tr>
              </thead>
              <tbody>
                {registeredCases.map((item) => (
                  <tr key={item.complaint_id}>
                    <td>
                      <button
                        type="button"
                        style={{
                          background: "#e0e7ff",
                          color: "#3730a3",
                          border: "none",
                          padding: "6px 12px",
                          borderRadius: "6px",
                          fontWeight: 700,
                          cursor: "pointer"
                        }}
                        onClick={() => openSavedCase(item.complaint_id)}
                      >
                        {item.complaint_id}
                      </button>
                    </td>
                    <td>{item.product_name || "—"}</td>
                    <td>{item.batch_number || "Not provided"}</td>
                    <td>
                      <span className={`status ${String(item.severity || "").toLowerCase()}`}>
                        {item.severity || "Unclassified"}
                      </span>
                    </td>
                    <td>{item.status || "Under Review"}</td>
                    <td>{item.updated_at ? item.updated_at.replace("T", " ").replace("+00:00", "") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h2>📋 Complaint Intelligence Report</h2>
        {loading && (
          <p className="loading">⏳ Triaging complaint details and risk levels...</p>
        )}

        {!complaintData.complaint ? (
          <div style={{ textAlign: "center", padding: "40px" }}>
            <h3>No Complaint Selected</h3>
            <p style={{ color: "#6b7280" }}>Submit a complaint or select a case above to inspect full intelligence data.</p>
          </div>
        ) : (
          <table>
            <tbody>
              <tr>
                <td>🏥 Customer / Facility</td>
                <td>{complaintData.customer_name || "Not specified"}</td>
              </tr>
              <tr>
                <td>💊 Product Name</td>
                <td>{complaintData.product_name || "Not specified"}</td>
              </tr>
              <tr>
                <td>⚖️ Dosage / Strength</td>
                <td>{complaintData.product_strength || "Not specified"}</td>
              </tr>
              <tr>
                <td>🏷️ Batch / Lot Number</td>
                <td>{complaintData.batch_number || "Not specified"}</td>
              </tr>
              <tr>
                <td>⚠️ Issue Description</td>
                <td>
                  {typeof complaintData.complaint === "object"
                    ? JSON.stringify(complaintData.complaint)
                    : complaintData.complaint}
                </td>
              </tr>
              <tr>
                <td>🚨 Triage Severity</td>
                <td>
                  <span className={`status ${complaintData.severity?.toLowerCase()}`}>
                    {complaintData.severity || "Not classified"}
                  </span>
                  {complaintData.severity_reason && (
                    <p style={{ margin: "8px 0 0", color: "#4b5563", fontSize: "14px" }}>
                      {complaintData.severity_reason}
                    </p>
                  )}
                </td>
              </tr>
              <tr>
                <td>⚠️ Risk Level</td>
                <td>{complaintData.risk_level || "Not assessed"}</td>
              </tr>
              <tr>
                <td>✅ Recommended Action</td>
                <td>{complaintData.recommended_action || "Standard investigation workflow"}</td>
              </tr>
              {complaintData.batch_signal && (
                <tr>
                  <td>⚠️ Batch Signal Alert</td>
                  <td>
                    {complaintData.batch_signal.report_count} reports registered for this batch in past 30 days.
                    {" "}{complaintData.batch_signal.review_note}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default App;
