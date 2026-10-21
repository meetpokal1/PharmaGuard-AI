import { useState, useEffect, useCallback } from "react";
import "./App.css";

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

  const [file, setFile] = useState(null);
  const [files, setFiles] = useState([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
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


  const saveComplaintData = (data) => {
    const safeData = { ...emptyComplaint, ...(data || {}) };
    setComplaintData(safeData);
  };

  const loadFiles = useCallback(async () => {
    try {
      const response = await fetch("http://127.0.0.1:8000/files");
      if (!response.ok) throw new Error("Could not load uploaded documents");
      const data = await response.json();
      setFiles(data.files || []);
    } catch (error) {
      console.log("File loading error:", error);
    }
  }, []);

  const loadRegister = useCallback(async () => {
    try {
      setRegisterLoading(true);
      const [casesResponse, signalsResponse, summaryResponse] = await Promise.all([
        fetch("http://127.0.0.1:8000/complaints?limit=50"),
        fetch("http://127.0.0.1:8000/analytics/batch-signals?days=30&min_reports=2"),
        fetch("http://127.0.0.1:8000/analytics/summary")
      ]);
      if (!casesResponse.ok || !signalsResponse.ok || !summaryResponse.ok) {
        throw new Error("The complaint register API is not available");
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
      console.log("Complaint register loading error:", error);
      setRegisterError("Live complaint register unavailable. Start the FastAPI backend and refresh.");
    } finally {
      setRegisterLoading(false);
    }
  }, []);


  const uploadFile = async () => {

    if (!file) {
      setMessage("Please select a PDF file first");
      return;
    }

    try {

      setUploading(true);
      setMessage("Uploading PDF...");

      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        "http://127.0.0.1:8000/upload",
        {
          method: "POST",
          body: formData
        }
      );

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      const data = await response.json();

      setMessage(data.message || "PDF uploaded successfully");

      setFile(null);

      setComplaintData(emptyComplaint);

      await loadFiles();

    } catch (error) {

      console.log("Upload error:", error);
      setMessage("Upload failed. Check backend.");

    } finally {
      setUploading(false);
    }
  };


  const analyzeComplaint = async (filename) => {

    try {

      setLoading(true);

      const extractResponse = await fetch(
        `http://127.0.0.1:8000/extract/${filename}`
      );

      const extracted = await extractResponse.json();

      const AIResponse = await fetch(
        "http://127.0.0.1:8000/chat",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            message: extracted.text
          })
        }
      );

      const aiData = await AIResponse.json();

      saveComplaintData(aiData.complaint);
      await loadRegister();

    } catch (error) {

      console.log("AI Error:", error);
      alert("Failed to analyze complaint");

    } finally {

      setLoading(false);

    }

  };

  const sendComplaint = async () => {

    if (!chatMessage.trim() && !chatFile) {
      alert("Please type a complaint or attach a PDF.");
      return;
    }

    try {

      setLoading(true);

      if (chatMessage.trim()) {

        const response = await fetch(
          "http://127.0.0.1:8000/chat",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              message: chatMessage
            })
          }
        );

        const data = await response.json();

        saveComplaintData(data.complaint);
        await loadRegister();

        setChatHistory(prev => [
          ...prev,
          {
            role: "user",
            content: chatMessage
          },
          {
            role: "assistant",
            content: data.reply
          }
        ]);
        setChatMessage("");

      } else if (chatFile) {

        const formData = new FormData();

        formData.append("file", chatFile);


        const uploadResponse = await fetch(
          "http://127.0.0.1:8000/upload",
          {
            method: "POST",
            body: formData
          }
        );


        const uploadData = await uploadResponse.json();


        const filename = uploadData.filename;

        setFiles(prev => [
          ...prev,
          filename
        ]);


        const extractResponse = await fetch(
          `http://127.0.0.1:8000/extract/${filename}`
        );

        const extractedData = await extractResponse.json();


        const AIResponse = await fetch(
          "http://127.0.0.1:8000/chat",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              message: extractedData.text
            })
          }
        );


        const AIData = await AIResponse.json();


        saveComplaintData(AIData.complaint);
        await loadRegister();

        setChatHistory(prev => [
          ...prev,
          {
            role: "user",
            content: `Uploaded PDF: ${chatFile.name}`
          },
          {
            role: "assistant",
            content: "I have analyzed your complaint PDF and extracted the details."
          }
        ]);


        setChatFile(null);

      }

    } catch (error) {

      console.log("Chat Error:", error);
      alert("Unable to process complaint.");

    } finally {

      setLoading(false);

    }

  };

  useEffect(() => {
    loadFiles();
    loadRegister();
  }, [loadFiles, loadRegister]);

  const openSavedCase = async (complaintId) => {
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/complaints/${encodeURIComponent(complaintId)}`
      );
      if (!response.ok) throw new Error("Could not open saved complaint");
      const data = await response.json();
      saveComplaintData(data.case);
      setShowChat(false);
      setMessage(`Opened saved case ${complaintId}`);
    } catch (error) {
      setRegisterError("Could not open this saved case. Check the backend.");
    }
  };

  return (
    <div className="container">

      <div className="header">
        <h1>🛡️ PharmaGuard AI</h1>
        <p>AI-Powered Complaint Intelligence Platform</p>
      </div>


      <div className="dashboard-cards">

        <div className="dashboard-card">
          <h3>Total Complaints</h3>
          <p>{caseSummary.total}</p>
        </div>

        <div className="dashboard-card">
          <h3>Critical Issues</h3>
          <p>{caseSummary.critical}</p>
        </div>

        <div className="dashboard-card">
          <h3>Pending</h3>
          <p>{caseSummary.pending}</p>
        </div>

        <div className="dashboard-card">
          <h3>Resolved</h3>
          <p>{caseSummary.resolved}</p>
        </div>

      </div>


      <div className="card">

        {!showChat ? (

          <>

            <h2>Create New Complaint</h2>

            <p>
              Describe your complaint in your own words or attach a complaint PDF.
            </p>

            <button
              onClick={() => setShowChat(true)}
            >
              ➕ Create Complaint
            </button>

          </>

        ) : (

          <>

            <h2>New Complaint</h2>


            {chatHistory.length > 0 && (

              <div className="chat-window">

                {chatHistory.map((msg, index) => (

                  <div
                    key={index}
                    className={
                      msg.role === "user"
                        ? "user-message"
                        : "ai-message"
                    }
                  >

                    <strong>
                      {msg.role === "user"
                        ? "You"
                        : "PharmaGuard AI"}
                    </strong>

                    <p>{msg.content}</p>

                  </div>

                ))}

              </div>

            )}

            <textarea
              rows="3"
              placeholder="Please Describe your Issue here"
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
            />

            <br />

            <label className="upload-btn">
              📎 Upload Complaint PDF
              <input
                type="file"
                accept="application/pdf"
                onChange={(e) => setChatFile(e.target.files[0])}
              />
            </label>

            <br />

            <button
              className="primary-btn"
              onClick={sendComplaint}
              disabled={loading}
            >
              {loading ? "Processing..." : "Send"}
            </button>

            <button
              className="secondary-btn"
              onClick={() => {

                setShowChat(false);
                setChatMessage("");
                setChatFile(null);

                setChatHistory([]);

                setComplaintData(emptyComplaint);

              }}
            >
              Cancel
            </button>

          </>

        )}

      </div>


      <div className="card">

        <h2>Uploaded Documents</h2>

        <ul>

          {files.length === 0 ? (

            <p>No complaint PDFs uploaded yet.</p>

          ) : (

            files.map((item) => (

              <li
                key={item}
                onClick={async () => {

                  setSelectedPDF(item);

                  window.open(
                    `http://127.0.0.1:8000/files/${item}`,
                    "_blank"
                  );

                  await analyzeComplaint(item);

                }}
              >
                📄 {item}
              </li>

            ))

          )}

        </ul>

        <p>
          Selected PDF: {selectedPDF}
        </p>

      </div>


      <div className="card">
        <h2>🗂️ Saved Complaint Register</h2>
        <p>Case records are stored in the local SQLite register and remain available after a backend restart.</p>
        {registerLoading && <p className="loading">Loading saved cases…</p>}
        {registerError && <p role="alert">{registerError}</p>}

        {batchSignals.length > 0 && (
          <div className="batch-signal-panel">
            <h3>⚠️ Potential repeated product/batch reports (last 30 days)</h3>
            <p>
              These are review signals, not confirmed defects. Verify the source cases and follow the organisation's approved quality process.
            </p>
            <ul>
              {batchSignals.map((signal) => (
                <li key={`${signal.product_key}-${signal.batch_key}`}>
                  <strong>{signal.product_name}</strong> · Batch <strong>{signal.batch_number}</strong>:
                  {" "}{signal.report_count} reports, {signal.critical_count} marked Critical.
                </li>
              ))}
            </ul>
          </div>
        )}

        {registeredCases.length === 0 ? (
          <p>No persisted complaint cases yet. Complete a complaint with a product name and description to create one.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Case ID</th>
                  <th>Product</th>
                  <th>Batch</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Last Updated (UTC)</th>
                </tr>
              </thead>
              <tbody>
                {registeredCases.map((item) => (
                  <tr key={item.complaint_id}>
                    <td>
                      <button type="button" onClick={() => openSavedCase(item.complaint_id)}>
                        {item.complaint_id}
                      </button>
                    </td>
                    <td>{item.product_name}</td>
                    <td>{item.batch_number || "Not provided"}</td>
                    <td>{item.severity}</td>
                    <td>{item.status}</td>
                    <td>{item.updated_at ? item.updated_at.replace("T", " ").replace("+00:00", "") : ""}</td>
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
          <p className="loading">
            ⏳ Analyzing complaint with AI...
          </p>
        )}


        {!complaintData.complaint ? (

          <div style={{ textAlign: "center", padding: "40px" }}>
            <h3>No Complaint Selected</h3>
            <p>Create a complaint or upload a PDF to view AI analysis.</p>
          </div>

        ) : (

          <table>

            <tbody>

              <tr>
                <td>🏥 Customer</td>
                <td>{complaintData.customer_name}</td>
              </tr>

              <tr>
                <td>💊 Product</td>
                <td>{complaintData.product_name}</td>
              </tr>

              <tr>
                <td>⚖️ Strength</td>
                <td>{complaintData.product_strength}</td>
              </tr>

              <tr>
                <td>🏷️ Batch Number</td>
                <td>{complaintData.batch_number}</td>
              </tr>

              <tr>
                <td>⚠️ Complaint</td>
                <td>
                  {typeof complaintData.complaint === "object"
                    ? JSON.stringify(complaintData.complaint)
                    : complaintData.complaint}
                </td>
              </tr>

              <tr>
                <td>🚨 Severity</td>
                <td>
                  <span className={`status ${complaintData.severity?.toLowerCase()}`}>
                    {complaintData.severity || "Not classified"}
                  </span>

                  {complaintData.severity_reason && (
                    <p>{complaintData.severity_reason}</p>
                  )}
                </td>
              </tr>

              <tr>
                <td>⚠️ Risk Level</td>
                <td>{complaintData.risk_level || "Not assessed"}</td>
              </tr>

              <tr>
                <td>✅ Recommended Action</td>
                <td>{complaintData.recommended_action}</td>
              </tr>

              {complaintData.batch_signal && (
                <tr>
                  <td>⚠️ Possible Batch Signal</td>
                  <td>
                    {complaintData.batch_signal.report_count} reports recorded for this product/batch in the last 30 days.
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