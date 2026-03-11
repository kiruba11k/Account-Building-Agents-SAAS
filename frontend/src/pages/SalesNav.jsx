import { useState } from "react";
import API from "../api";
import { useNavigate } from "react-router-dom";

export default function SalesNav() {

  const navigate = useNavigate();

  const [loading, setLoading] = useState(false);

  const [sections, setSections] = useState({
    geo: true,
    industry: true,
    company: true,
    funding: false,
    keywords: false,
    extraction: false
  });

  const toggle = (key) => {
    setSections({ ...sections, [key]: !sections[key] });
  };

  const [formData, setFormData] = useState({

    request_name: "",

    geo_country: "",
    geo_region_state: "",
    geo_city: "",

    industry_include: "",
    industry_exclude: "",

    org_type: "",

    employee_min: "",
    employee_max: "",

    revenue_min_usd: "",
    revenue_max_usd: "",

    keywords_include: "",
    keywords_exclude: "",

    funding_stage_include: "",

    founded_year_min: "",
    founded_year_max: "",

    company_status: "Active",

    source_priority: "SalesNav>Google",

    max_results: 1000,

    dedupe_key: "domain",

    output_fields_profile: "standard_v1",

    notes: ""
  });

  const handleChange = (e) => {

    const { name, value } = e.target;

    setFormData({
      ...formData,
      [name]: value
    });

  };

  const launchAgent = async () => {

    setLoading(true);

    try {

      const res = await API.post("/api/run-salesnav", formData);

      navigate(`/results/${res.data.request_id}`);

    } catch (err) {

      alert("Agent launch failed");

    }

    setLoading(false);

  };

  const removeFilter = (key) => {

    setFormData({
      ...formData,
      [key]: ""
    });

  };

  const activeFilters = Object.entries(formData)
    .filter(([k, v]) => v && k !== "request_name" && k !== "notes");

  return (

    <div className="max-w-6xl">

      <h2 className="text-2xl font-bold mb-6">
        Sales Navigator Lead Builder
      </h2>

      <div className="bg-white rounded-2xl shadow-lg p-8 space-y-6">

        {/* Request Name */}

        <div>

          <label className="font-semibold block mb-2">
            Request Name
          </label>

          <input
            name="request_name"
            value={formData.request_name}
            onChange={handleChange}
            className="w-full border px-4 py-2 rounded-lg"
            placeholder="Example: US SaaS Companies"
          />

        </div>

        {/* Active Filters */}

        {activeFilters.length > 0 && (

          <div>

            <p className="font-semibold mb-2">Active Filters</p>

            <div className="flex flex-wrap gap-2">

              {activeFilters.map(([key, value]) => (

                <span
                  key={key}
                  className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm cursor-pointer"
                  onClick={() => removeFilter(key)}
                >
                  {value} ✕
                </span>

              ))}

            </div>

          </div>

        )}

        {/* Geography */}

        <div>

          <button
            onClick={() => toggle("geo")}
            className="font-semibold text-lg"
          >
            Geography {sections.geo ? "▾" : "▸"}
          </button>

          {sections.geo && (

            <div className="grid grid-cols-3 gap-4 mt-4">

              <input
                name="geo_country"
                value={formData.geo_country}
                onChange={handleChange}
                placeholder="Country"
                className="border px-4 py-2 rounded-lg"
              />

              <input
                name="geo_region_state"
                value={formData.geo_region_state}
                onChange={handleChange}
                placeholder="State"
                className="border px-4 py-2 rounded-lg"
              />

              <input
                name="geo_city"
                value={formData.geo_city}
                onChange={handleChange}
                placeholder="City"
                className="border px-4 py-2 rounded-lg"
              />

            </div>

          )}

        </div>

        {/* Industry */}

        <div>

          <button
            onClick={() => toggle("industry")}
            className="font-semibold text-lg"
          >
            Industry {sections.industry ? "▾" : "▸"}
          </button>

          {sections.industry && (

            <div className="grid grid-cols-2 gap-4 mt-4">

              <input
                name="industry_include"
                value={formData.industry_include}
                onChange={handleChange}
                placeholder="Include Industries"
                className="border px-4 py-2 rounded-lg"
              />

              <input
                name="industry_exclude"
                value={formData.industry_exclude}
                onChange={handleChange}
                placeholder="Exclude Industries"
                className="border px-4 py-2 rounded-lg"
              />

            </div>

          )}

        </div>

        {/* Company Size */}

        <div>

          <button
            onClick={() => toggle("company")}
            className="font-semibold text-lg"
          >
            Company Size {sections.company ? "▾" : "▸"}
          </button>

          {sections.company && (

            <div className="grid grid-cols-2 gap-4 mt-4">

              <input
                name="employee_min"
                value={formData.employee_min}
                onChange={handleChange}
                placeholder="Employee Min"
                className="border px-4 py-2 rounded-lg"
              />

              <input
                name="employee_max"
                value={formData.employee_max}
                onChange={handleChange}
                placeholder="Employee Max"
                className="border px-4 py-2 rounded-lg"
              />

              <input
                name="revenue_min_usd"
                value={formData.revenue_min_usd}
                onChange={handleChange}
                placeholder="Revenue Min USD"
                className="border px-4 py-2 rounded-lg"
              />

              <input
                name="revenue_max_usd"
                value={formData.revenue_max_usd}
                onChange={handleChange}
                placeholder="Revenue Max USD"
                className="border px-4 py-2 rounded-lg"
              />

            </div>

          )}

        </div>

        {/* Keywords */}

        <div>

          <button
            onClick={() => toggle("keywords")}
            className="font-semibold text-lg"
          >
            Keywords {sections.keywords ? "▾" : "▸"}
          </button>

          {sections.keywords && (

            <div className="grid grid-cols-2 gap-4 mt-4">

              <input
                name="keywords_include"
                value={formData.keywords_include}
                onChange={handleChange}
                placeholder="Include Keywords"
                className="border px-4 py-2 rounded-lg"
              />

              <input
                name="keywords_exclude"
                value={formData.keywords_exclude}
                onChange={handleChange}
                placeholder="Exclude Keywords"
                className="border px-4 py-2 rounded-lg"
              />

            </div>

          )}

        </div>

        {/* Funding */}

        <div>

          <button
            onClick={() => toggle("funding")}
            className="font-semibold text-lg"
          >
            Funding {sections.funding ? "▾" : "▸"}
          </button>

          {sections.funding && (

            <div className="grid grid-cols-2 gap-4 mt-4">

              <input
                name="funding_stage_include"
                value={formData.funding_stage_include}
                onChange={handleChange}
                placeholder="Funding Stage"
                className="border px-4 py-2 rounded-lg"
              />

              <input
                name="founded_year_min"
                value={formData.founded_year_min}
                onChange={handleChange}
                placeholder="Founded Year Min"
                className="border px-4 py-2 rounded-lg"
              />

              <input
                name="founded_year_max"
                value={formData.founded_year_max}
                onChange={handleChange}
                placeholder="Founded Year Max"
                className="border px-4 py-2 rounded-lg"
              />

            </div>

          )}

        </div>

        {/* Extraction Settings */}

        <div>

          <button
            onClick={() => toggle("extraction")}
            className="font-semibold text-lg"
          >
            Extraction Settings {sections.extraction ? "▾" : "▸"}
          </button>

          {sections.extraction && (

            <div className="grid grid-cols-2 gap-4 mt-4">

              <input
                name="max_results"
                value={formData.max_results}
                onChange={handleChange}
                placeholder="Max Results"
                className="border px-4 py-2 rounded-lg"
              />

              <input
                name="dedupe_key"
                value={formData.dedupe_key}
                onChange={handleChange}
                placeholder="Dedupe Key"
                className="border px-4 py-2 rounded-lg"
              />

              <textarea
                name="notes"
                value={formData.notes}
                onChange={handleChange}
                placeholder="Notes"
                className="border px-4 py-2 rounded-lg col-span-2"
              />

            </div>

          )}

        </div>

        {/* Live Query Preview */}

        <div className="bg-gray-100 p-4 rounded-lg text-sm">

          <p className="font-semibold mb-1">Query Preview</p>

          Searching for companies in <b>{formData.geo_country || "any location"}</b>
          {formData.industry_include && (
            <> within <b>{formData.industry_include}</b> industry</>
          )}
          {formData.employee_min && (
            <> with at least <b>{formData.employee_min}</b> employees</>
          )}.

        </div>

        {/* Launch */}

        <button
          onClick={launchAgent}
          className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition"
        >
          {loading ? "Launching Agent..." : "Launch Agent"}
        </button>

      </div>

    </div>

  );

}
