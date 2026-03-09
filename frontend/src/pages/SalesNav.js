import { useState } from "react";
import API from "../api";

export default function SalesNav() {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);

  const launch = async () => {
    setLoading(true);
    await API.post("/api/run-salesnav", { request_name: name });
    setLoading(false);
    alert("SalesNav Launched!");
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
          className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition"
        >
          {loading ? "Launching..." : "Launch Agent"}
        </button>
      </div>
    </div>
  );
}
