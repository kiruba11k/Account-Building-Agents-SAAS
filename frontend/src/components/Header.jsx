export default function Header() {
  return (
    <header className="glass-panel neon-ring relative z-10 mx-4 mt-4 flex items-center justify-between rounded-3xl px-6 py-4">
      <div className="flex items-center gap-3">
        <span className="material-symbols-rounded rounded-xl bg-cyan-300/20 p-2 text-cyan-100">dashboard</span>
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">Dashboard</h2>
          <p className="text-xs uppercase tracking-[0.28em] text-cyan-100/70">AI outbound intelligence</p>
        </div>
      </div>
      <div className="rounded-full border border-emerald-300/35 bg-emerald-400/15 px-4 py-1.5 text-xs font-semibold tracking-wide text-emerald-100">
        SaaS MVP v1
      </div>
    </header>
  );
}
