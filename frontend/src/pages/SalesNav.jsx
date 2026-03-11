import { useState } from "react";
import API from "../api";
import { useNavigate } from "react-router-dom";

export default function SalesNav() {

  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const launch = async () => {

    if (!name) {
      alert("Please enter request name");
      return;
    }

    setLoading(true);

    try {

      const res = await API.post("/api/run-salesnav", {
        request_name: name
      });

      const requestId = res.data.request_id;

      // redirect to results page
      navigate(`/results/${requestId}`);

    } catch (err) {

      console.error(err);
      alert("Failed to launch agent");

    }

    setLoading(false);

  };

  return (

    <div className="max-w-3xl">

      <div className="bg-white rounded-2xl shadow-lg p-8">

        <h3 className="text-xl font-semibold mb-6">
          Launch Sales Navigator Agent
        </h3>

        <input
          className="w-full border rounded-lg px-4 py-2 mb-4 focus:ring-2 focus:ring-blue-500"
          placeholder="Request Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        <button
          onClick={launch}
          disabled={loading}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
        >
          {loading ? "Launching..." : "Launch Agent"}
        </button>

      </div>

    </div>

  );

}
