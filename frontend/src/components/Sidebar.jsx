import { Link, useLocation } from "react-router-dom";

export default function Sidebar() {
  const location = useLocation();

  const menu = [
    { path: "/", label: "LinkedIn Sales Nav Scraper"},
    { path: "/google", label: "Google Scraper Lead Gen" },
    { path: "/enrichment", label: "Firmographic Enricher" },
    { path: "/requests", label: "Requests"},
  ];

  return (
    <aside className="glass-panel neon-ring relative z-10 m-4 hidden w-72 rounded-3xl p-6 md:block">
      <div className="mb-10">
        <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/80">LeadStrategus</p>
        <h1 className="float-soft mt-2 text-3xl font-black leading-tight text-white">Account Discovery & List Building</h1>
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
              <span className="text-lg">{item.icon}</span>
              <span className="font-medium">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
