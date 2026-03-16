import { useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api";
import MultiValueInput from "../components/MultiValueInput";

export default function GoogleAgent() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [searchTerms, setSearchTerms] = useState(["restaurant"]);
  const [categories, setCategories] = useState([]);

  const [formData, setFormData] = useState({
    request_name: "",
    location: "New York, USA",
    max_places: 50,
    language: "English",
    scrapePlaceDetailPage: true,
    includeWebResults: true,
    skipClosedPlaces: true,
    company_contacts_enrichment: true,
    max_leads_per_place: 0,
  });

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const launchAgent = async () => {
    setLoading(true);
    try {
      const payload = {
        ...formData,
        search_terms: searchTerms,
        categories,
      };
      const res = await API.post("/api/run-google-discovery", payload);
      navigate(`/results/${res.data.request_id}`);
    } catch {
      alert("Google Discovery launch failed");
    }
    setLoading(false);
  };

  return (
    <div className="grid gap-7 lg:grid-cols-[400px_1fr]">
      <div className="glass-panel card-hover sticky top-6 h-fit rounded-3xl p-6">
        <h2 className="mb-6 text-xl font-bold text-white">Google Discovery Filters</h2>

        <input
          name="request_name"
          value={formData.request_name}
          onChange={handleChange}
          placeholder="Request Name"
          className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
        />

        <div className="mt-5 space-y-4">
          <MultiValueInput label="Search Terms" values={searchTerms} setValues={setSearchTerms} />
          <input
            name="location"
            value={formData.location}
            onChange={handleChange}
            placeholder="Location"
            className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
          />
          <input
            name="max_places"
            type="number"
            value={formData.max_places}
            onChange={handleChange}
            placeholder="Max places"
            className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
          />
          <input
            name="language"
            value={formData.language}
            onChange={handleChange}
            placeholder="Language"
            className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
          />

          <MultiValueInput label="Categories" values={categories} setValues={setCategories} />

          <label className="flex items-center gap-2 text-slate-200 text-sm">
            <input type="checkbox" name="scrapePlaceDetailPage" checked={formData.scrapePlaceDetailPage} onChange={handleChange} />
            Scrape place detail page
          </label>
          <label className="flex items-center gap-2 text-slate-200 text-sm">
            <input type="checkbox" name="includeWebResults" checked={formData.includeWebResults} onChange={handleChange} />
            Include web results
          </label>
          <label className="flex items-center gap-2 text-slate-200 text-sm">
            <input type="checkbox" name="skipClosedPlaces" checked={formData.skipClosedPlaces} onChange={handleChange} />
            Skip closed places
          </label>
          <label className="flex items-center gap-2 text-slate-200 text-sm">
            <input type="checkbox" name="company_contacts_enrichment" checked={formData.company_contacts_enrichment} onChange={handleChange} />
            Company contacts enrichment
          </label>
        </div>
      </div>

      <div className="glass-panel card-hover rounded-3xl p-8">
        <h3 className="text-2xl font-bold text-white">Google Discovery Agent</h3>
        <p className="mt-4 text-slate-200/90 leading-7">
          <b className="text-cyan-200">crawler-google-places</b> with the synchronous
          dataset endpoint for GTM enrichment-friendly output.
        </p>

        <div className="mt-6 rounded-2xl border border-cyan-200/30 bg-cyan-300/10 p-4 text-sm text-cyan-100">
          Recommended endpoint: <code>/run-sync-get-dataset-items</code> for immediate lead rows.
        </div>

        <button
          onClick={launchAgent}
          className="mt-8 rounded-2xl bg-gradient-to-r from-cyan-400 via-blue-500 to-violet-500 px-7 py-3 text-sm font-semibold text-white shadow-[0_10px_25px_rgba(59,130,246,0.45)] transition hover:scale-[1.02]"
        >
          {loading ? "Launching Agent..." : "Launch Google Discovery"}
        </button>
      </div>
    </div>
  );
}
