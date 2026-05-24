import { useState } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [pdfUrl, setPdfUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [responseType, setResponseType] = useState("");

  const askTeacher = async () => {
    if (!question.trim()) {
      alert("Please enter a question.");
      return;
    }

    setLoading(true);
    setAnswer("");
    setPdfUrl("");
    setResponseType("");

    try {
      const response = await axios.post("http://localhost:8000/ask", {
        question: question,
      });

      setAnswer(response.data.answer);
      setPdfUrl(response.data.pdf_url);
      setResponseType(response.data.type);
    } catch (error) {
      console.error(error);
      setAnswer("Something went wrong. Please check backend server.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="container">
        <header className="header">
          <h1>AI Education Teacher Agent</h1>
          <p>
            Ask education-related questions. Get explanations, notes, quizzes,
            paper sets, and official exam information.
          </p>
        </header>

        <section className="card">
          <label>Your Question</label>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Example: Create maths paper set for 8th class"
          />

          <button onClick={askTeacher} disabled={loading}>
            {loading ? "Generating..." : "Ask Teacher Agent"}
          </button>
        </section>

        {answer && (
          <section className="result-card">
            <div className="badge">{responseType}</div>

            <h2>Response</h2>
            <p>{answer}</p>

            {pdfUrl && (
              <a className="download-btn" href={pdfUrl} target="_blank">
                Download PDF
              </a>
            )}
          </section>
        )}

        <section className="examples">
          <h3>Try these examples</h3>
          <ul>
            <li>Explain probability for 10th class</li>
            <li>Create biology paper set for 5th class</li>
            <li>Give revision notes on photosynthesis</li>
            <li>When will NEET 2026 be conducted?</li>
          </ul>
        </section>
      </div>
    </div>
  );
}

export default App;