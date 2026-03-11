import { Link, useLocation } from "react-router-dom";

export default function Sidebar() {
  const location = useLocation();

  const menu = [
    { path: "/", label: "Sales Navigator", icon: "🔵" },
    { path: "/google", label: "Google Agent", icon: "🟡" },
    { path: "/enrichment", label: "Enrichment", icon: "🟢" },
    { path: "/requests", label: "Requests", icon: "📁" },
  ];

  return (
    <div className="w-64 bg-gray-900 text-white p-6">
      <h1 className="text-2xl font-bold mb-10">LeadForge</h1>

      <nav className="space-y-4">
        {menu.map(item => (
          <Link
            key={item.path}
            to={item.path}
            className={`block px-4 py-2 rounded-lg transition ${
              location.pathname === item.path
                ? "bg-gray-700"
                : "hover:bg-gray-800"
            }`}
          >
            {item.icon} {item.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
