import { useEffect, useState } from "react";
import API from "../api";
import StatusBadge from "../components/StatusBadge";

export default function Requests() {
  const [data, setData] = useState([]);

  useEffect(() => {
    const interval = setInterval(() => {
      API.get("/api/requests").then(res => setData(res.data));
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
            <th>Total</th>
            <th></th>
          </tr>
        </thead>

        <tbody>
          {data.map(r => (
            <tr key={r.id} className="border-b">
              <td className="py-4">{r.request_name}</td>
              <td><StatusBadge status={r.status} /></td>
              <td>{r.total_results}</td>
              <td>
                {r.status === "Completed" && (
                  <a
                    href={`${process.env.REACT_APP_API_URL}/api/download/${r.id}`}
                    className="text-blue-600 hover:underline"
                  >
                    Download CSV
                  </a>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
