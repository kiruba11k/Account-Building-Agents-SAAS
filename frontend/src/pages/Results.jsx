import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import { markSalesNavRequestFinal } from "../utils/sessionMemory";

const AGENT_META = {
  salesnav: {
    title: "LinkedIn Sales Nav Scraper Results",
    accent: "from-cyan-400 via-blue-500 to-violet-500",
  },
  google: {
    title: "Google Scraper Lead Gen Results",
    accent: "from-emerald-400 via-teal-500 to-cyan-500",
  },
  enrichment: {
    title: "Firmographic Enricher Results",
    accent: "from-fuchsia-500 via-violet-500 to-indigo-500",
  },
};

function fingerprint(row) {
  return Object.values(row || {})
    .find((value) => typeof value === "string" && value.trim())
    ?.toString()
    .trim()
    .toLowerCase();
}

function valueToText(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function Results() {
  const { id } = useParams();

  const [status, setStatus] = useState({});
  const [results, setResults] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [liveCount, setLiveCount] = useState(0);
  const [streamState, setStreamState] = useState("connecting");

  const limit = 50;
  const seenRef = useRef(new Set());

  const streamBase = useMemo(() => {
    const base = api?.defaults?.baseURL || "";
    if (!base) return window.location.origin;
    return base.endsWith("/") ? base.slice(0, -1) : base;
  }, []);

  const orderedColumns = useMemo(() => {
    const map = new Map();
    results.forEach((row) => {
      Object.keys(row || {}).forEach((key) => {
        if (!["id", "request_id"].includes(key) && !map.has(key)) {
          map.set(key, key);
        }
      });
    });

    return Array.from(map.keys());
  }, [results]);

  const agentMeta = AGENT_META[status.agent_type] || {
    title: "Agent Results",
    accent: "from-cyan-400 via-blue-500 to-violet-500",
  };

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
    setTotal(res.data.total || 0);
  };

  useEffect(() => {
    loadStatus();
    loadResults(page);

    const interval = setInterval(() => {
      loadStatus();
      loadResults(page);
    }, 5000);

    return () => clearInterval(interval);
  }, [id, page]);

  useEffect(() => {
    if (!id) return;

    const source = new EventSource(`${streamBase}/api/stream/${id}/events`);

    source.onopen = () => setStreamState("connected");
    source.onerror = () => setStreamState("reconnecting");

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
            setResults((prev) => [payload, ...prev].slice(0, limit));
          }
        }
      } catch {
        // ignore malformed stream events
      }
    };

    return () => source.close();
  }, [id, page, streamBase]);

  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="space-y-6">
      <div className="glass-panel rounded-3xl p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-white">{agentMeta.title}</h2>
            <p className="mt-2 text-sm text-slate-200/90">
              Request #{id} • Status: <b>{status.phase || "starting"}</b> • Stream: <b>{streamState}</b>
            </p>
          </div>

          <div className="text-sm text-slate-200">
            Total rows: <b>{total}</b> • Live updates: <b>{liveCount}</b>
          </div>
        </div>

        <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-white/15">
          <div
            className={`h-2 rounded-full bg-gradient-to-r ${agentMeta.accent}`}
            style={{ width: `${status.progress || 0}%` }}
          />
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <a
            href={`${streamBase}/api/download/${id}`}
            className="rounded-xl bg-white/15 px-4 py-2 text-sm font-semibold text-white hover:bg-white/25"
          >
            Download CSV
          </a>
          <Link to="/requests" className="rounded-xl border border-white/25 px-4 py-2 text-sm text-slate-100 hover:bg-white/10">
            Back to all requests
          </Link>
        </div>
      </div>

      <div className="glass-panel overflow-hidden rounded-3xl">
        <div className="overflow-x-auto">
          <table className="min-w-full table-auto border-collapse text-left text-sm text-slate-100">
            <thead className="bg-white/10 text-xs uppercase tracking-wide text-cyan-100">
              <tr>
                {orderedColumns.map((col) => (
                  <th key={col} className="whitespace-nowrap px-4 py-3 font-semibold">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.map((row, rowIndex) => (
                <tr key={row.id || `${fingerprint(row)}-${rowIndex}`} className="border-t border-white/10">
                  {orderedColumns.map((col) => (
                    <td key={`${rowIndex}-${col}`} className="max-w-[300px] px-4 py-3 align-top text-slate-200">
                      <span className="break-words">{valueToText(row[col])}</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!results.length && (
          <div className="p-6 text-sm text-slate-300">No rows yet. This page will update live while the background agent keeps running.</div>
        )}
      </div>

      <div className="flex items-center justify-center gap-4">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className="rounded-lg border border-white/20 px-4 py-2 disabled:opacity-50"
        >
          Previous
        </button>
        <span className="text-sm text-slate-200">Page {page} / {totalPages}</span>
        <button
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page >= totalPages}
          className="rounded-lg border border-white/20 px-4 py-2 disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}
