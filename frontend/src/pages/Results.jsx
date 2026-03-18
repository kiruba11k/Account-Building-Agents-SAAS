import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api";
import { markSalesNavRequestFinal } from "../utils/sessionMemory";

function fingerprint(row) {
  return (
    row.company_url ||
    row.regular_company_url ||
    row.website ||
    row.company_name ||
    row.name ||
    ""
  )
    .toString()
    .trim()
    .toLowerCase();
}

export default function Results() {
  const { id } = useParams();

  const [status, setStatus] = useState({});
  const [results, setResults] = useState([]);
  const [page, setPage] = useState(1);
  const [liveCount, setLiveCount] = useState(0);
  const [streamState, setStreamState] = useState("connecting");

  const limit = 50;
  const seenRef = useRef(new Set());

  const streamBase = useMemo(() => {
    const base = api?.defaults?.baseURL || "";
    if (!base) return window.location.origin;
    return base.endsWith("/") ? base.slice(0, -1) : base;
  }, []);

  useEffect(() => {
    setPage(1);
    setStatus({});
    setResults([]);
    setLiveCount(0);
    setStreamState("connecting");
    seenRef.current = new Set();
  }, [id]);

  const loadStatus = async () => {
    const res = await api.get(`/api/request/${id}`);
    setStatus(res.data);

    if (["Completed", "Failed", "Timeout"].includes(res.data?.status)) {
      markSalesNavRequestFinal(id, res.data.status);
    }
  };

  const loadResults = async (pageNumber) => {
    const res = await api.get(`/api/results/${id}?page=${pageNumber}&limit=${limit}`);
    const incoming = res.data.results || [];

    incoming.forEach((row) => {
      const fp = fingerprint(row);
      if (fp) seenRef.current.add(fp);
    });

    setResults(incoming);
  };

  useEffect(() => {
    loadStatus();
    loadResults(page);

    const interval = setInterval(() => {
      loadStatus();
      loadResults(page);
    }, 6000);

    return () => clearInterval(interval);
  }, [id, page]);

  useEffect(() => {
    if (!id) return;

    const source = new EventSource(`${streamBase}/api/stream/${id}/events`);

    source.onopen = () => {
      setStreamState("connected");
    };

    source.onerror = () => {
      setStreamState("reconnecting");
    };

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);

        if (payload.type === "status" || payload.type === "end") {
          setStatus((prev) => ({ ...prev, ...payload }));
          return;
        }

        if (payload.type === "company") {
          const fp = fingerprint(payload);
          if (!fp || seenRef.current.has(fp)) return;

          seenRef.current.add(fp);
          setLiveCount((count) => count + 1);

          if (page === 1) {
            setResults((prev) => {
              const merged = [payload, ...prev];
              return merged.slice(0, limit);
            });
          }
        }
      } catch {
        // ignore malformed stream events
      }
    };

    return () => {
      source.close();
    };
  }, [id, page, streamBase]);

  return (
    <div>
      <h2>Results</h2>

      <div>
        <p>Status: {status.phase || "starting"}</p>
        <p>
          Stream: <b>{streamState}</b> • Live companies: <b>{liveCount}</b>
        </p>

        <div style={{ background: "#ddd", height: "10px" }}>
          <div
            style={{
              width: `${status.progress || 0}%`,
              background: "green",
              height: "10px",
            }}
          />
        </div>
      </div>

      <table border="1">
        <thead>
          <tr>
            <th>Company</th>
            <th>Domain</th>
            <th>Industry</th>
            <th>Employees</th>
            <th>Revenue</th>
          </tr>
        </thead>

        <tbody>
          {results.map((r, i) => (
            <tr key={r.id || `${fingerprint(r)}-${i}`}>
              <td>{r.company_name || r.name || "-"}</td>
              <td>{r.company_url || r.website || r.domain || "-"}</td>
              <td>{r.industry || "-"}</td>
              <td>{r.employees_count || r.headcount || "-"}</td>
              <td>{r.revenue || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ marginTop: "10px" }}>
        <button onClick={() => setPage(page - 1)} disabled={page === 1}>
          Previous
        </button>

        <span style={{ margin: "0 10px" }}>Page {page}</span>

        <button onClick={() => setPage(page + 1)}>Next</button>
      </div>

      <br />

      <a href={`${streamBase}/api/download/${id}`}>Download CSV</a>
    </div>
  );
}
