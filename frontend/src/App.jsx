import { useState, useEffect } from "react";
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


  const saveComplaintData = (data) => {
    const safeData = { ...emptyComplaint, ...(data || {}) };
    setComplaintData(safeData);
  };

  const loadFiles = async () => {

    try {

      const response = await fetch(
        "http://127.0.0.1:8000/files"
      );

      const data = await response.json();

      setFiles(data.files || []);

    } catch (error) {

      console.log("File loading error:", error);

    }

  };


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

  return (
    <div className="container">

      <div className="header">
        <h1>🛡️ PharmaGuard AI</h1>
        <p>AI-Powered Complaint Intelligence Platform</p>
      </div>


      <div className="dashboard-cards">

        <div className="dashboard-card">
          <h3>Total Complaints</h3>
          <p>25</p>
        </div>

        <div className="dashboard-card">
          <h3>Critical Issues</h3>
          <p>5</p>
        </div>

        <div className="dashboard-card">
          <h3>Pending</h3>
          <p>2</p>
        </div>

        <div className="dashboard-card">
          <h3>Resolved</h3>
          <p>18</p>
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

            </tbody>

          </table>

        )}
      </div>

    </div>
  );
}

export default App;