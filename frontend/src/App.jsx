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
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <Header />
          <div className="p-8">
            <Routes>
              <Route path="/" element={<SalesNav />} />
              <Route path="/google" element={<GoogleAgent />} />
              <Route path="/enrichment" element={<Enrichment />} />
              <Route path="/requests" element={<Requests />} />
              <Route path="/results/:id" element={<Results />} />
            </Routes>
          </div>
        </div>
      </div>
    </BrowserRouter>
  );
}
