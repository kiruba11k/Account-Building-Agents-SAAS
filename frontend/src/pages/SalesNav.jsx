import { useState } from "react";
import MultiValueInput from "../components/MultiValueInput";
import API from "../api";
import { useNavigate } from "react-router-dom";
import MultiValueInput from "../components/MultiValueInput";

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

    const payload = {

      ...formData,

      geo_country: countries.join(";"),

      industry_include: industriesInclude.join(";"),
      industry_exclude: industriesExclude.join(";"),

      keywords_include: keywordsInclude.join(";"),
      keywords_exclude: keywordsExclude.join(";")

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

    <div className="flex gap-8">

      {/* LEFT FILTER PANEL */}

      <div className="w-96 bg-white rounded-xl shadow p-6 space-y-6 sticky top-6 h-fit">

        <h2 className="text-xl font-bold">
          Filters
        </h2>

        <input
          name="request_name"
          value={formData.request_name}
          onChange={handleChange}
          placeholder="Request Name"
          className="border px-3 py-2 rounded w-full"
        />

        <MultiValueInput
          label="Countries"
          values={countries}
          setValues={setCountries}
        />

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
            className="border px-3 py-2 rounded"
          />

          <input
            name="employee_max"
            value={formData.employee_max}
            onChange={handleChange}
            placeholder="Employee Max"
            className="border px-3 py-2 rounded"
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
          className="border px-3 py-2 rounded w-full"
        />

      </div>

      {/* RIGHT PANEL */}

      <div className="flex-1 bg-white rounded-xl shadow p-8 space-y-6">

        <h2 className="text-xl font-bold">
          Query Preview
        </h2>

        <p className="text-gray-700">

          Searching companies in

          <b> {countries.length ? countries.join(", ") : "any location"} </b>

          {industriesInclude.length > 0 && (
            <> within <b>{industriesInclude.join(", ")}</b> industry</>
          )}

          {formData.employee_min && (
            <> with at least <b>{formData.employee_min}</b> employees</>
          )}

          {keywordsInclude.length > 0 && (
            <> matching <b>{keywordsInclude.join(", ")}</b></>
          )}

        </p>

        <div className="bg-gray-100 rounded-lg p-4 text-sm">

          Estimated results will depend on your filters.

        </div>

        <button
          onClick={launchAgent}
          className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700"
        >
          {loading ? "Launching Agent..." : "Launch Agent"}
        </button>

      </div>

    </div>

  );

}
