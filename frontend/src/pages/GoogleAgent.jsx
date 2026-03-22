import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api";
import MultiValueInput from "../components/MultiValueInput";
import {
  getGoogleActiveRequest,
  getGoogleDraft,
  markSalesNavRequestFinal,
  rememberGoogleActiveRequest,
  saveGoogleDraft,
} from "../utils/sessionMemory";

const defaultForm = {
  request_name: "",
  location: "New York, USA",
  max_places: 50,
  language: "en",
  scrapePlaceDetailPage: false,
  includeWebResults: false,
  skipClosedPlaces: false,
  company_contacts_enrichment: false,
  max_leads_per_place: 0,
  scrapeDirectories: false,
  scrapeImageAuthors: false,
  scrapeReviewsPersonalData: true,
  scrapeTableReservationProvider: false,
  apify_actor_id: "compass/crawler-google-places",
};

export default function GoogleAgent() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [searchTerms, setSearchTerms] = useState([]);
  const [categories, setCategories] = useState([]);
  const [activeRequest, setActiveRequest] = useState(null);
  const [formData, setFormData] = useState(defaultForm);
  const [rawActorInput, setRawActorInput] = useState("");
  const [rawActorInputError, setRawActorInputError] = useState("");

  useEffect(() => {
    const savedDraft = getGoogleDraft();
    if (savedDraft) {
      setFormData({ ...defaultForm, ...(savedDraft.formData || {}) });
      if (typeof savedDraft.rawActorInput === "string") {
        setRawActorInput(savedDraft.rawActorInput);
      }
      if (Array.isArray(savedDraft.searchTerms) && savedDraft.searchTerms.length > 0) {
        setSearchTerms(savedDraft.searchTerms);
      }
      if (Array.isArray(savedDraft.categories)) {
        setCategories(savedDraft.categories);
      }
    }

    const active = getGoogleActiveRequest();
    if (active?.request_id) {
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
    }
  }, []);

  useEffect(() => {
    saveGoogleDraft({ formData, searchTerms, categories, rawActorInput });
  }, [formData, searchTerms, categories, rawActorInput]);

  const endpointLabel = useMemo(
    () => "actor.start + run polling + dataset.iterate_items",
    []
  );

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const launchAgent = async () => {
    let rawApifyInput = null;
    if (rawActorInput.trim()) {
      try {
        rawApifyInput = JSON.parse(rawActorInput);
        setRawActorInputError("");
      } catch {
        setRawActorInputError("Raw actor JSON is invalid. Fix JSON before launching.");
        return;
      }
    }

    setLoading(true);
    try {
      const payload = {
        ...formData,
        search_terms: searchTerms,
        categories,
        raw_apify_input: rawApifyInput,
      };
      const res = await API.post("/api/run-google-discovery", payload);
      rememberGoogleActiveRequest(res.data.request_id);
      setActiveRequest({ request_id: String(res.data.request_id), status: "Running" });
      navigate(`/results/${res.data.request_id}`);
    } catch {
      alert("Google Discovery launch failed");
    }
    setLoading(false);
  };

  return (
    <div className="grid gap-7 lg:grid-cols-[410px_1fr]">
      <div className="glass-panel card-hover sticky top-6 h-fit rounded-3xl p-6">
        <h2 className="mb-6 text-xl font-bold text-white">Google Scraper Lead-Gen Filters</h2>

        <input
          name="request_name"
          value={formData.request_name}
          onChange={handleChange}
          placeholder="Request Name"
          className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
        />

        <div className="mt-5 space-y-4">
          <MultiValueInput
            label="Search Terms"
            values={searchTerms}
            setValues={setSearchTerms}
            placeholder="Type a niche (e.g. AI companies, schools, law firms) and press Enter"
          />
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
            placeholder="Language code (e.g. en, hi, fr, zh-CN)"
            className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
          />
          <input
            name="apify_actor_id"
            value={formData.apify_actor_id}
            onChange={handleChange}
            placeholder="Apify actor ID"
            className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
          />

          <MultiValueInput label="Categories" values={categories} setValues={setCategories} />

          <label className="flex items-center gap-2 text-sm text-slate-200">
            <input type="checkbox" name="scrapePlaceDetailPage" checked={formData.scrapePlaceDetailPage} onChange={handleChange} />
            Scrape place detail page
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-200">
            <input type="checkbox" name="includeWebResults" checked={formData.includeWebResults} onChange={handleChange} />
            Include web results
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-200">
            <input type="checkbox" name="skipClosedPlaces" checked={formData.skipClosedPlaces} onChange={handleChange} />
            Skip closed places
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-200">
            <input type="checkbox" name="company_contacts_enrichment" checked={formData.company_contacts_enrichment} onChange={handleChange} />
            Company contacts enrichment
          </label>
          <input
            name="max_leads_per_place"
            type="number"
            value={formData.max_leads_per_place}
            onChange={handleChange}
            min={0}
            placeholder="Maximum leads enrichment records per place"
            className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
          />
          <label className="flex items-center gap-2 text-sm text-slate-200">
            <input type="checkbox" name="scrapeDirectories" checked={formData.scrapeDirectories} onChange={handleChange} />
            Scrape directories
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-200">
            <input type="checkbox" name="scrapeImageAuthors" checked={formData.scrapeImageAuthors} onChange={handleChange} />
            Include image authors
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-200">
            <input type="checkbox" name="scrapeReviewsPersonalData" checked={formData.scrapeReviewsPersonalData} onChange={handleChange} />
            Include reviewers' data
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-200">
            <input type="checkbox" name="scrapeTableReservationProvider" checked={formData.scrapeTableReservationProvider} onChange={handleChange} />
            Scrape table reservation providers
          </label>

          <div>
            <label className="mb-2 block text-xs uppercase tracking-wide text-slate-300">
              Raw  input override (optional JSON)
            </label>
            <textarea
              value={rawActorInput}
              onChange={(e) => {
                setRawActorInput(e.target.value);
                if (rawActorInputError) {
                  setRawActorInputError("");
                }
              }}
              rows={10}
              placeholder='{"searchMatching":"all","scrapeSocialMediaProfiles":{"facebooks":false}}'
              className="w-full rounded-xl border border-white/15 bg-slate-950/70 px-3 py-2.5 font-mono text-xs text-slate-100 placeholder:text-slate-400 focus:border-cyan-300/70 focus:outline-none"
            />
            {rawActorInputError && (
              <p className="mt-2 text-xs text-rose-300">{rawActorInputError}</p>
            )}
          </div>
        </div>
      </div>

      <div className="glass-panel card-hover rounded-3xl p-8">
        <h3 className="text-2xl font-bold text-white">Google Discovery Agent (SaaS Mode)</h3>
        <p className="mt-4 leading-7 text-slate-200/90">
          This flow runs in the backend background worker, so switching pages or opening other jobs will not stop your Google lead generation run.
        </p>



        {activeRequest?.request_id && (
          <div className="mt-4 rounded-2xl border border-emerald-200/30 bg-emerald-300/10 p-4 text-sm text-emerald-100">
            Active Google request: <b>#{activeRequest.request_id}</b>
            <button
              onClick={() => navigate(`/results/${activeRequest.request_id}`)}
              className="ml-3 rounded-lg bg-emerald-500/30 px-3 py-1 font-semibold text-emerald-50 hover:bg-emerald-500/50"
            >
              Resume tracking
            </button>
          </div>
        )}

        <button
          onClick={launchAgent}
          disabled={loading}
          className="mt-8 rounded-2xl bg-gradient-to-r from-cyan-400 via-blue-500 to-violet-500 px-7 py-3 text-sm font-semibold text-white shadow-[0_10px_25px_rgba(59,130,246,0.45)] transition hover:scale-[1.02]"
        >
          {loading ? "Launching Agent..." : "Launch Google Discovery"}
        </button>
      </div>
    </div>
  );
}
