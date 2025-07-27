import React, { useState, useCallback } from "react";
import "./App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const FileUpload = ({ onFileUpload, isProcessing }) => {
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onFileUpload(e.dataTransfer.files[0]);
    }
  }, [onFileUpload]);

  const handleChange = useCallback((e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      onFileUpload(e.target.files[0]);
    }
  }, [onFileUpload]);

  return (
    <div className="w-full max-w-2xl mx-auto mb-8">
      <div
        className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-300 ${
          dragActive
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 hover:border-gray-400"
        } ${isProcessing ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".pdf,image/*"
          onChange={handleChange}
          disabled={isProcessing}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
        />
        
        <div className="space-y-4">
          <div className="text-6xl text-gray-400">📄</div>
          <div>
            <h3 className="text-xl font-semibold text-gray-700 mb-2">
              Upload Title Insurance Document
            </h3>
            <p className="text-gray-500 mb-4">
              Drag & drop your PDF or image file here, or click to browse
            </p>
            <p className="text-sm text-gray-400">
              Supported formats: PDF, JPG, PNG, TIFF, BMP (Max 10MB)
            </p>
          </div>
          
          {!isProcessing && (
            <button className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors">
              Choose File
            </button>
          )}
          
          {isProcessing && (
            <div className="flex items-center justify-center space-x-2">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
              <span className="text-blue-600 font-medium">Processing...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const ResultDisplay = ({ result }) => {
  const fields = [
    { key: "effective_date", label: "Effective Date", icon: "📅" },
    { key: "insured_party", label: "Insured Party", icon: "👤" },
    { key: "underwriter", label: "Underwriter", icon: "🏢" },
    { key: "legal_description", label: "Legal Description", icon: "📍" },
    { key: "exceptions", label: "Exceptions", icon: "⚠️" },
    { key: "policy_amount", label: "Policy Amount", icon: "💰" },
  ];

  return (
    <div className="w-full max-w-4xl mx-auto bg-white rounded-xl shadow-lg p-8">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-800 mb-2">
          Document Analysis Results
        </h2>
        <p className="text-gray-600">
          Extracted information from your title insurance document
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {fields.map((field) => (
          <div
            key={field.key}
            className="bg-gray-50 rounded-lg p-4 border border-gray-200"
          >
            <div className="flex items-center mb-2">
              <span className="text-2xl mr-2">{field.icon}</span>
              <h3 className="font-semibold text-gray-700">{field.label}</h3>
            </div>
            <div className="text-gray-800">
              {result[field.key] ? (
                <p className="break-words">{result[field.key]}</p>
              ) : (
                <p className="text-gray-400 italic">Not found</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {result.compliance_notes && result.compliance_notes.length > 0 && (
        <div className="bg-blue-50 rounded-lg p-6 border border-blue-200">
          <h3 className="font-semibold text-blue-800 mb-4 flex items-center">
            <span className="text-2xl mr-2">📋</span>
            Compliance Notes
          </h3>
          <ul className="space-y-2">
            {result.compliance_notes.map((note, index) => (
              <li key={index} className="text-blue-700 flex items-start">
                <span className="mr-2 mt-1">•</span>
                <span>{note}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-8 text-center">
        <button
          onClick={() => window.location.reload()}
          className="bg-green-600 text-white px-6 py-3 rounded-lg hover:bg-green-700 transition-colors font-medium"
        >
          Analyze Another Document
        </button>
      </div>
    </div>
  );
};

const ErrorDisplay = ({ error, onRetry }) => (
  <div className="w-full max-w-2xl mx-auto bg-red-50 border border-red-200 rounded-xl p-6">
    <div className="text-center">
      <div className="text-4xl mb-4">❌</div>
      <h3 className="text-lg font-semibold text-red-800 mb-2">
        Processing Error
      </h3>
      <p className="text-red-600 mb-4">{error}</p>
      <button
        onClick={onRetry}
        className="bg-red-600 text-white px-6 py-2 rounded-lg hover:bg-red-700 transition-colors"
      >
        Try Again
      </button>
    </div>
  </div>
);

function App() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFileUpload = async (file) => {
    setIsProcessing(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await axios.post(`${API}/analyze-document`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        timeout: 60000, // 60 second timeout
      });

      setResult(response.data);
    } catch (err) {
      console.error("Error analyzing document:", err);
      let errorMessage = "An unexpected error occurred while processing your document.";
      
      if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.message.includes("timeout")) {
        errorMessage = "Document processing timed out. Please try again with a smaller file.";
      } else if (err.message.includes("Network Error")) {
        errorMessage = "Network error. Please check your connection and try again.";
      }
      
      setError(errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRetry = () => {
    setError(null);
    setResult(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-800 mb-4">
            🔍 Mortgage Document Analyzer
          </h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Upload your title insurance or title policy document to extract key information 
            and receive compliance insights powered by AI.
          </p>
          <div className="mt-4 text-sm text-gray-500">
            Stateless • Privacy-focused • No document storage
          </div>
        </div>

        {/* Main Content */}
        <div className="flex flex-col items-center space-y-8">
          {!result && !error && (
            <FileUpload onFileUpload={handleFileUpload} isProcessing={isProcessing} />
          )}

          {error && <ErrorDisplay error={error} onRetry={handleRetry} />}

          {result && <ResultDisplay result={result} />}
        </div>

        {/* Footer */}
        <div className="text-center mt-16 text-gray-500 text-sm">
          <p>
            Powered by OpenAI GPT-4o-mini and Tesseract OCR • 
            Built for mortgage professionals
          </p>
        </div>
      </div>
    </div>
  );
}

export default App;