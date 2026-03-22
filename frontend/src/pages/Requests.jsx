import { useEffect, useState } from "react";
import API from "../api";
import StatusBadge from "../components/StatusBadge";
import { Link } from "react-router-dom";

export default function Requests() {
  const [data, setData] = useState([]);

  useEffect(() => {
    const load = () => {
      API.get("/api/requests").then((res) => {
        const ordered = [...(res.data || [])].sort((a, b) => Number(b.id || 0) - Number(a.id || 0));
        setData(ordered);
      });
    };

    load();

    const interval = setInterval(() => {
      load();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="glass-panel rounded-3xl p-6 md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-2xl font-bold text-white">All Requests</h3>
          <p className="mt-2 text-sm text-slate-200/90">
            Live request tracker for every agent run in your workspace.
          </p>
        </div>
        <div className="rounded-xl border border-cyan-300/30 bg-cyan-300/10 px-4 py-2 text-sm text-cyan-100">
          Total requests: <b>{data.length}</b>
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded-2xl border border-white/15 bg-slate-950/30">
        <div className="max-h-[560px] overflow-auto">
          <table className="min-w-full border-collapse text-left text-sm text-slate-100">
            <thead className="sticky top-0 z-10 bg-slate-900/90 text-xs uppercase tracking-wide text-cyan-100 backdrop-blur">
              <tr>
                <th className="px-4 py-3 font-semibold">Name</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Agent</th>
                <th className="px-4 py-3 font-semibold">Total</th>
                <th className="px-4 py-3 font-semibold text-right">Actions</th>
              </tr>
            </thead>

            <tbody>
              {data.map((r) => (
                <tr key={r.id} className="border-t border-white/10 transition hover:bg-white/5">
                  <td className="px-4 py-4">
                    <div className="font-medium text-white">{r.request_name || `Request #${r.id}`}</div>
                    <div className="mt-1 text-xs text-slate-300">ID #{r.id}</div>
                  </td>
                  <td className="px-4 py-4"><StatusBadge status={r.status} /></td>
                  <td className="px-4 py-4 text-sm capitalize text-slate-200">{r.agent_type || "salesnav"}</td>
                  <td className="px-4 py-4 text-slate-100">{r.total_results ?? 0}</td>
                  <td className="px-4 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        to={`/results/${r.id}`}
                        className="rounded-lg border border-blue-300/40 bg-blue-400/10 px-3 py-1.5 text-xs font-semibold text-blue-100 transition hover:bg-blue-400/20"
                      >
                        Open Results
                      </Link>
                      {r.status === "Completed" && (
                        <a
                          href={`${API.defaults.baseURL}/api/download/${r.id}`}
                          className="rounded-lg border border-emerald-300/40 bg-emerald-400/10 px-3 py-1.5 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/20"
                        >
                          Download CSV
                        </a>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {data.length === 0 && (
        <p className="mt-4 text-sm text-slate-300">
          No requests yet. Launch an agent to see runs here.
        </p>
      )}
    </div>
  );
}
