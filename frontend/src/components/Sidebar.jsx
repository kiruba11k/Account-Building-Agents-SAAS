import { Link, useLocation } from "react-router-dom";

export default function Sidebar() {
  const location = useLocation();

  const menu = [
    { path: "/", label: "Sales Navigator", icon: "travel_explore" },
    { path: "/google", label: "Google Agent", icon: "smart_toy" },
    { path: "/enrichment", label: "Enrichment", icon: "auto_awesome" },
    { path: "/requests", label: "Requests", icon: "folder_open" },
  ];

  return (
    <aside className="glass-panel neon-ring relative z-10 m-4 hidden w-72 rounded-3xl p-6 md:block">
      <div className="mb-10">
        <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/80">LeadForge</p>
        <h1 className="float-soft mt-2 text-3xl font-extrabold leading-tight text-white">Growth Console</h1>
      </div>

      <nav className="space-y-3">
        {menu.map((item) => {
          const active = location.pathname === item.path;

          return (
            <Link
              key={item.path}
              to={item.path}
              className={`card-hover flex items-center gap-3 rounded-2xl border px-4 py-3 transition ${
                active
                  ? "border-cyan-200/50 bg-cyan-300/20 text-cyan-100"
                  : "border-white/10 bg-white/5 text-slate-200 hover:border-cyan-100/40 hover:bg-white/15"
              }`}
            >
              <span className="material-symbols-rounded text-[20px] leading-none">{item.icon}</span>
              <span className="font-medium tracking-wide">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
