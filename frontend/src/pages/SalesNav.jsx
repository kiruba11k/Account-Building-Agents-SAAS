import { useState } from "react";
import MultiValueInput from "../components/MultiValueInput";
import API from "../api";
import { useNavigate } from "react-router-dom";

export default function SalesNav() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const [countries, setCountries] = useState([]);
  const [industriesInclude, setIndustriesInclude] = useState([]);
  const [industriesExclude, setIndustriesExclude] = useState([]);
  const [keywordsInclude, setKeywordsInclude] = useState([]);
  const [keywordsExclude, setKeywordsExclude] = useState([]);

  const [formData, setFormData] = useState({
    request_name: "",
    employee_min: "",
    employee_max: "",
    revenue_min_usd: "",
    revenue_max_usd: "",
    founded_year_min: "",
    founded_year_max: "",
    max_results: 1000,
    notes: "",
    company_status: "Active",
    source_priority: "SalesNav>Google",
    dedupe_key: "domain",
    output_fields_profile: "standard_v1",
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value,
    });
  };

  const launchAgent = async () => {
    setLoading(true);

    const payload = {
      ...formData,
      geo_country: countries.join(";"),
      industry_include: industriesInclude.join(";"),
      industry_exclude: industriesExclude.join(";"),
      keywords_include: keywordsInclude.join(";"),
      keywords_exclude: keywordsExclude.join(";"),
    };

    try {
      const res = await API.post("/api/run-salesnav", payload);
      navigate(`/results/${res.data.request_id}`);
    } catch {
      alert("Agent launch failed");
    }

    setLoading(false);
  };

  return (
    <div className="grid gap-7 lg:grid-cols-[400px_1fr]">
      <div className="glass-panel card-hover sticky top-6 h-fit rounded-3xl p-6">
        <h2 className="mb-6 text-xl font-bold text-white">Filters</h2>

        <input
          name="request_name"
          value={formData.request_name}
          onChange={handleChange}
          placeholder="Request Name"
          className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
        />

        <div className="mt-5 space-y-5">
          <MultiValueInput label="Countries" values={countries} setValues={setCountries} />
          <MultiValueInput
            label="Include Industries"
            values={industriesInclude}
            setValues={setIndustriesInclude}
          />
          <MultiValueInput
            label="Exclude Industries"
            values={industriesExclude}
            setValues={setIndustriesExclude}
          />

          <div className="grid grid-cols-2 gap-2">
            <input
              name="employee_min"
              value={formData.employee_min}
              onChange={handleChange}
              placeholder="Employee Min"
              className="rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
            />

            <input
              name="employee_max"
              value={formData.employee_max}
              onChange={handleChange}
              placeholder="Employee Max"
              className="rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
            />
          </div>

          <MultiValueInput
            label="Include Keywords"
            values={keywordsInclude}
            setValues={setKeywordsInclude}
          />

          <MultiValueInput
            label="Exclude Keywords"
            values={keywordsExclude}
            setValues={setKeywordsExclude}
          />

          <input
            name="max_results"
            value={formData.max_results}
            onChange={handleChange}
            placeholder="Max Results"
            className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
          />
        </div>
      </div>

      <div className="glass-panel card-hover rounded-3xl p-8">
        <h2 className="text-2xl font-bold text-white">Query Preview</h2>

        <p className="mt-4 leading-7 text-slate-200/90">
          Searching companies in
          <b className="text-cyan-200"> {countries.length ? countries.join(", ") : "any location"} </b>
          {industriesInclude.length > 0 && (
            <>
              {" "}
              within <b className="text-cyan-200">{industriesInclude.join(", ")}</b> industry
            </>
          )}
          {formData.employee_min && (
            <>
              {" "}
              with at least <b className="text-cyan-200">{formData.employee_min}</b> employees
            </>
          )}
          {keywordsInclude.length > 0 && (
            <>
              {" "}
              matching <b className="text-cyan-200">{keywordsInclude.join(", ")}</b>
            </>
          )}
        </p>

        <div className="mt-6 rounded-2xl border border-indigo-200/20 bg-indigo-300/10 p-4 text-sm text-indigo-100">
          Estimated results will depend on your filters.
        </div>

        <button
          onClick={launchAgent}
          className="mt-8 rounded-2xl bg-gradient-to-r from-cyan-400 via-blue-500 to-violet-500 px-7 py-3 text-sm font-semibold text-white shadow-[0_10px_25px_rgba(59,130,246,0.45)] transition hover:scale-[1.02]"
        >
          {loading ? "Launching Agent..." : "Launch Agent"}
        </button>
      </div>
    </div>
  );
}
