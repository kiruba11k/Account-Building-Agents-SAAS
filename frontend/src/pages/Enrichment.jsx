import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api";
import MultiValueInput from "../components/MultiValueInput";
import {
  getEnrichmentActiveRequest,
  markSalesNavRequestFinal,
  rememberEnrichmentActiveRequest,
} from "../utils/sessionMemory";

function splitCsvLine(line, delimiter) {
  const values = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];

    if (char === '"') {
      const nextChar = line[i + 1];
      if (inQuotes && nextChar === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === delimiter && !inQuotes) {
      values.push(current.trim());
      current = "";
      continue;
    }

    current += char;
  }

  values.push(current.trim());
  return values;
}

function parseCompanyInputsFromCsv(csvText) {
  const cleaned = String(csvText || "").replace(/^\uFEFF/, "");
  const lines = cleaned
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (!lines.length) return [];

  const firstLine = lines[0];
  const delimiter = firstLine.includes("\t") ? "\t" : firstLine.includes(";") ? ";" : ",";
  const headerCells = splitCsvLine(firstLine, delimiter).map((cell) => cell.toLowerCase());

  const companyHeaderCandidates = ["company", "company_name", "company url", "company_url", "url", "website", "domain"];
  let companyColumnIndex = headerCells.findIndex((value) => companyHeaderCandidates.includes(value));
  const hasHeader = companyColumnIndex !== -1;

  if (companyColumnIndex < 0) {
    companyColumnIndex = 0;
  }

  const dataLines = hasHeader ? lines.slice(1) : lines;
  const values = dataLines
    .map((line) => splitCsvLine(line, delimiter)[companyColumnIndex])
    .map((value) => String(value || "").trim())
    .filter(Boolean);

  return Array.from(new Set(values));
}

export default function Enrichment() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [companyInputs, setCompanyInputs] = useState([]);
  const [requestName, setRequestName] = useState("");
  const [activeRequest, setActiveRequest] = useState(null);
  const [uploadMessage, setUploadMessage] = useState("");

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

  const totalQueued = useMemo(() => companyInputs.length, [companyInputs]);

  const handleCsvUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const parsed = parseCompanyInputsFromCsv(text);

      if (!parsed.length) {
        setUploadMessage("No company values found in the uploaded CSV.");
        return;
      }

      setCompanyInputs((prev) => Array.from(new Set([...prev, ...parsed])));
      setUploadMessage(`Imported ${parsed.length} companies from ${file.name}.`);
    } catch {
      setUploadMessage("Unable to read CSV file.");
    } finally {
      event.target.value = "";
    }
  };

  const launch = async () => {
    if (!companyInputs.length) {
      alert("Add at least one company name or website");
      return;
    }

    setLoading(true);
    try {
      const res = await API.post("/api/run-firmographic-enricher", {
        request_name: requestName,
        company_inputs: companyInputs,
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
          <MultiValueInput
            label="Company Names or Website URLs"
            values={companyInputs}
            setValues={setCompanyInputs}
            placeholder="e.g. Stripe or stripe.com"
          />
          <div className="mt-4 rounded-xl border border-white/15 bg-white/5 p-3">
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-300">Bulk enrichment CSV</label>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={handleCsvUpload}
              className="mt-2 block w-full rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-xs text-slate-100 file:mr-3 file:rounded-md file:border-0 file:bg-fuchsia-500/60 file:px-3 file:py-1 file:text-xs file:font-semibold file:text-white"
            />
            <p className="mt-2 text-xs text-slate-300">Uses the <b>company</b> column if present; otherwise uses the first column.</p>
            {uploadMessage && <p className="mt-2 text-xs text-emerald-200">{uploadMessage}</p>}
            <p className="mt-2 text-xs text-slate-300">Queued companies: <b>{totalQueued}</b></p>
          </div>
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
