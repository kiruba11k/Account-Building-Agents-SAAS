import { useEffect, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_API_URL;

export default function ResultsPage({ requestId }) {

  const [status, setStatus] = useState({});
  const [results, setResults] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const limit = 50;

  // ---------------------------
  // Load request status
  // ---------------------------

  const loadStatus = async () => {

    const res = await axios.get(`${API}/api/request/${requestId}`);

    setStatus(res.data);

  };

  // ---------------------------
  // Load results
  // ---------------------------

  const loadResults = async (pageNumber) => {

    const res = await axios.get(
      `${API}/api/results/${requestId}?page=${pageNumber}&limit=${limit}`
    );

    setResults(res.data.results);
    setTotal(res.data.total);

  };

  // ---------------------------
  // Live polling
  // ---------------------------

  useEffect(() => {

    loadStatus();
    loadResults(page);

    const interval = setInterval(() => {

      loadStatus();

      if (status.progress !== 100) {
        loadResults(page);
      }

    }, 5000);

    return () => clearInterval(interval);

  }, [page]);

  // ---------------------------
  // Pagination
  // ---------------------------

  const totalPages = Math.ceil(total / limit);

  const nextPage = () => {
    if (page < totalPages) setPage(page + 1);
  };

  const prevPage = () => {
    if (page > 1) setPage(page - 1);
  };

  return (
    <div className="p-8">

      <h1 className="text-2xl font-bold mb-6">
        Lead Results
      </h1>

      {/* Progress Bar */}

      <div className="mb-6">

        <div className="flex justify-between text-sm mb-1">
          <span>Status: {status.phase}</span>
          <span>{status.progress}%</span>
        </div>

        <div className="w-full bg-gray-200 rounded h-4">
          <div
            className="bg-blue-500 h-4 rounded"
            style={{ width: `${status.progress || 0}%` }}
          />
        </div>

      </div>

      {/* CSV Download */}

      <a
        href={`${API}/api/download/${requestId}`}
        className="bg-green-600 text-white px-4 py-2 rounded mb-6 inline-block"
      >
        Download CSV
      </a>

      {/* Results Table */}

      <table className="w-full border mt-4">

        <thead className="bg-gray-100">

          <tr>
            <th className="p-2 border">Company</th>
            <th className="p-2 border">Domain</th>
            <th className="p-2 border">Industry</th>
            <th className="p-2 border">Employees</th>
            <th className="p-2 border">Revenue</th>
            <th className="p-2 border">Location</th>
            <th className="p-2 border">Confidence</th>
          </tr>

        </thead>

        <tbody>

          {results.map((r, i) => (

            <tr key={i} className="text-sm">

              <td className="border p-2">{r.name}</td>

              <td className="border p-2">{r.domain}</td>

              <td className="border p-2">{r.industry}</td>

              <td className="border p-2">{r.headcount}</td>

              <td className="border p-2">{r.revenue}</td>

              <td className="border p-2">{r.headquarters}</td>

              <td className="border p-2">{r.confidence_score}</td>

            </tr>

          ))}

        </tbody>

      </table>

      {/* Pagination */}

      <div className="flex justify-center gap-4 mt-6">

        <button
          onClick={prevPage}
          className="px-4 py-2 bg-gray-200 rounded"
        >
          Previous
        </button>

        <span className="px-4 py-2">
          Page {page} / {totalPages || 1}
        </span>

        <button
          onClick={nextPage}
          className="px-4 py-2 bg-gray-200 rounded"
        >
          Next
        </button>

      </div>

    </div>
  );
}
