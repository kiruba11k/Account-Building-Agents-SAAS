import { useEffect, useState } from "react";
import API from "../api";
import StatusBadge from "../components/StatusBadge";
import { Link } from "react-router-dom";

export default function Requests() {
  const [data, setData] = useState([]);

  useEffect(() => {
    const load = () => {
      API.get("/api/requests").then((res) => {
        const ordered = [...(res.data || [])].sort((a, b) => Number(b.id || 0) - Number(a.id || 0));
        setData(ordered);
      });
    };

    load();

    const interval = setInterval(() => {
      load();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-white rounded-2xl shadow-lg p-8">
      <h3 className="text-xl font-semibold mb-6">
        All Requests
      </h3>

      <table className="w-full text-left">
        <thead>
          <tr className="border-b text-gray-500 text-sm">
            <th className="pb-3">Name</th>
            <th>Status</th>
            <th>Agent</th>
            <th>Total</th>
            <th></th>
          </tr>
        </thead>

        <tbody>
          {data.map(r => (
            <tr key={r.id} className="border-b">
              <td className="py-4">{r.request_name}</td>
              <td><StatusBadge status={r.status} /></td>
              <td className="text-sm capitalize text-gray-600">{r.agent_type || "salesnav"}</td>
              <td>{r.total_results}</td>
              <td>
                <div className="flex items-center gap-3">
                  <Link to={`/results/${r.id}`} className="text-blue-600 hover:underline">
                    Open Results
                  </Link>
                  {r.status === "Completed" && (
                    <a
                      href={`${API.defaults.baseURL}/api/download/${r.id}`}
                      className="text-green-700 hover:underline"
                    >
                      Download CSV
                    </a>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
