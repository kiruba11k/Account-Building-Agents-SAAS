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
    keywords: true,
    funding: false,
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

    employee_min: "",
    employee_max: "",

    revenue_min_usd: "",
    revenue_max_usd: "",

    keywords_include: "",
    keywords_exclude: "",

    funding_stage_include: "",
    founded_year_min: "",
    founded_year_max: "",

    max_results: 1000,

    notes: "",

    company_status: "Active",
    source_priority: "SalesNav>Google",
    dedupe_key: "domain",
    output_fields_profile: "standard_v1"
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

    } catch {

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

    <div className="flex gap-8">

      {/* LEFT FILTER SIDEBAR */}

      <div className="w-96 bg-white rounded-xl shadow p-6 space-y-6 sticky top-6 h-fit">

        <h2 className="text-xl font-bold">
          Filters
        </h2>

        {/* Request Name */}

        <input
          name="request_name"
          value={formData.request_name}
          onChange={handleChange}
          placeholder="Request Name"
          className="border px-3 py-2 rounded w-full"
        />

        {/* Geography */}

        <div>

          <button
            onClick={() => toggle("geo")}
            className="font-semibold"
          >
            Geography {sections.geo ? "▾" : "▸"}
          </button>

          {sections.geo && (

            <div className="space-y-2 mt-3">

              <input
                name="geo_country"
                value={formData.geo_country}
                onChange={handleChange}
                placeholder="Country"
                className="border px-3 py-2 rounded w-full"
              />

              <input
                name="geo_region_state"
                value={formData.geo_region_state}
                onChange={handleChange}
                placeholder="State"
                className="border px-3 py-2 rounded w-full"
              />

              <input
                name="geo_city"
                value={formData.geo_city}
                onChange={handleChange}
                placeholder="City"
                className="border px-3 py-2 rounded w-full"
              />

            </div>

          )}

        </div>

        {/* Industry */}

        <div>

          <button
            onClick={() => toggle("industry")}
            className="font-semibold"
          >
            Industry {sections.industry ? "▾" : "▸"}
          </button>

          {sections.industry && (

            <div className="space-y-2 mt-3">

              <input
                name="industry_include"
                value={formData.industry_include}
                onChange={handleChange}
                placeholder="Include Industries"
                className="border px-3 py-2 rounded w-full"
              />

              <input
                name="industry_exclude"
                value={formData.industry_exclude}
                onChange={handleChange}
                placeholder="Exclude Industries"
                className="border px-3 py-2 rounded w-full"
              />

            </div>

          )}

        </div>

        {/* Company Size */}

        <div>

          <button
            onClick={() => toggle("company")}
            className="font-semibold"
          >
            Company Size {sections.company ? "▾" : "▸"}
          </button>

          {sections.company && (

            <div className="grid grid-cols-2 gap-2 mt-3">

              <input
                name="employee_min"
                value={formData.employee_min}
                onChange={handleChange}
                placeholder="Min"
                className="border px-3 py-2 rounded"
              />

              <input
                name="employee_max"
                value={formData.employee_max}
                onChange={handleChange}
                placeholder="Max"
                className="border px-3 py-2 rounded"
              />

            </div>

          )}

        </div>

        {/* Keywords */}

        <div>

          <button
            onClick={() => toggle("keywords")}
            className="font-semibold"
          >
            Keywords {sections.keywords ? "▾" : "▸"}
          </button>

          {sections.keywords && (

            <div className="space-y-2 mt-3">

              <input
                name="keywords_include"
                value={formData.keywords_include}
                onChange={handleChange}
                placeholder="Include Keywords"
                className="border px-3 py-2 rounded w-full"
              />

              <input
                name="keywords_exclude"
                value={formData.keywords_exclude}
                onChange={handleChange}
                placeholder="Exclude Keywords"
                className="border px-3 py-2 rounded w-full"
              />

            </div>

          )}

        </div>

      </div>

      {/* RIGHT RESULTS PANEL */}

      <div className="flex-1 bg-white rounded-xl shadow p-8 space-y-6">

        <h2 className="text-xl font-bold">
          Query Preview
        </h2>

        <p className="text-gray-700">

          Searching companies in <b>{formData.geo_country || "any location"}</b>

          {formData.industry_include && (
            <> within <b>{formData.industry_include}</b> industry</>
          )}

          {formData.employee_min && (
            <> with at least <b>{formData.employee_min}</b> employees</>
          )}

          {formData.keywords_include && (
            <> matching <b>{formData.keywords_include}</b></>
          )}

        </p>

        {/* Active Filters */}

        <div className="flex flex-wrap gap-2">

          {activeFilters.map(([key, value]) => (

            <span
              key={key}
              className="bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-sm cursor-pointer"
              onClick={() => removeFilter(key)}
            >
              {value} ✕
            </span>

          ))}

        </div>

        {/* Estimated results box */}

        <div className="bg-gray-100 rounded-lg p-4">

          <p className="text-sm text-gray-600">
            Estimated results depend on your filters.
          </p>

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
