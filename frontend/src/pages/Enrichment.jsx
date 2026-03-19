import { useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api";
import MultiValueInput from "../components/MultiValueInput";
import {
  getEnrichmentActiveRequest,
  markSalesNavRequestFinal,
  rememberEnrichmentActiveRequest,
} from "../utils/sessionMemory";
import { useEffect } from "react";

export default function Enrichment() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [urls, setUrls] = useState([]);
  const [requestName, setRequestName] = useState("");
  const [activeRequest, setActiveRequest] = useState(null);

  useEffect(() => {
    const active = getEnrichmentActiveRequest();
    if (!active?.request_id) return;

    setActiveRequest(active);
    API.get(`/api/request/${active.request_id}`)
      .then((res) => {
        if (["Completed", "Failed", "Timeout"].includes(res?.data?.status)) {
          markSalesNavRequestFinal(active.request_id, res.data.status);
          setActiveRequest(null);
        }
      })
      .catch(() => {
        // ignore status refresh failure
      });
  }, []);

  const launch = async () => {
    if (!urls.length) {
      alert("Add at least one LinkedIn company URL");
      return;
    }

    setLoading(true);
    try {
      const res = await API.post("/api/run-firmographic-enricher", {
        request_name: requestName,
        linkedin_urls: urls,
      });
      rememberEnrichmentActiveRequest(res.data.request_id);
      setActiveRequest({ request_id: String(res.data.request_id), status: "Running" });
      navigate(`/results/${res.data.request_id}`);
    } catch {
      alert("Failed to launch firmographic enricher");
    }
    setLoading(false);
  };

  return (
    <div className="grid gap-7 lg:grid-cols-[420px_1fr]">
      <div className="glass-panel card-hover sticky top-6 h-fit rounded-3xl p-6">
        <h2 className="mb-6 text-xl font-bold text-white">Firmographic Enricher</h2>
        <input
          placeholder="Request Name"
          value={requestName}
          onChange={(e) => setRequestName(e.target.value)}
          className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70"
        />
        <div className="mt-5">
          <MultiValueInput label="LinkedIn Company URLs" values={urls} setValues={setUrls} />
        </div>
      </div>

      <div className="glass-panel card-hover rounded-3xl p-8">
        <h3 className="text-2xl font-bold text-white">Run enrichment in background</h3>
        <p className="mt-4 text-slate-200/90">
          Trigger enrichment once and continue working in other tabs/agents. Results stream live on a dedicated page with dynamic columns and CSV export.
        </p>
        {activeRequest?.request_id && (
          <div className="mt-4 rounded-2xl border border-fuchsia-200/30 bg-fuchsia-300/10 p-4 text-sm text-fuchsia-100">
            Active Enrichment request: <b>#{activeRequest.request_id}</b>
            <button
              onClick={() => navigate(`/results/${activeRequest.request_id}`)}
              className="ml-3 rounded-lg bg-fuchsia-500/30 px-3 py-1 font-semibold text-fuchsia-50 hover:bg-fuchsia-500/50"
            >
              Resume tracking
            </button>
          </div>
        )}
        <button
          onClick={launch}
          className="mt-8 rounded-2xl bg-gradient-to-r from-fuchsia-500 via-violet-500 to-indigo-500 px-7 py-3 text-sm font-semibold text-white"
        >
          {loading ? "Launching..." : "Launch Firmographic Enricher"}
        </button>
      </div>
    </div>
  );
}
