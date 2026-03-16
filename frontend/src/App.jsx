import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import SalesNav from "./pages/SalesNav";
import GoogleAgent from "./pages/GoogleAgent";
import Enrichment from "./pages/Enrichment";
import Requests from "./pages/Requests";
import Results from "./pages/Results";

export default function App() {
  return (
    <BrowserRouter>
      <div className="relative flex min-h-screen overflow-hidden text-slate-100">
        <div className="pointer-events-none absolute -left-10 top-10 h-56 w-56 rounded-full bg-cyan-400/30 blur-3xl" />
        <div className="pointer-events-none absolute right-0 top-56 h-64 w-64 rounded-full bg-purple-500/30 blur-3xl" />

        <Sidebar />

        <div className="relative z-10 flex flex-1 flex-col">
          <Header />
          <main className="p-6 md:p-8">
            <Routes>
              <Route path="/" element={<SalesNav />} />
              <Route path="/google" element={<GoogleAgent />} />
              <Route path="/enrichment" element={<Enrichment />} />
              <Route path="/requests" element={<Requests />} />
              <Route path="/results/:id" element={<Results />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}
