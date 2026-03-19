import { useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api";
import MultiValueInput from "../components/MultiValueInput";

export default function Enrichment() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [urls, setUrls] = useState([]);
  const [requestName, setRequestName] = useState("");

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
