import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import SalesNav from "./pages/SalesNav";
import GoogleAgent from "./pages/GoogleAgent";
import Enrichment from "./pages/Enrichment";
import Requests from "./pages/Requests";

export default function App() {
  return (
    <BrowserRouter>
      <div style={{display:"flex"}}>
        <Sidebar />
        <div style={{flex:1,padding:20}}>
          <Routes>
            <Route path="/" element={<SalesNav />} />
            <Route path="/google" element={<GoogleAgent />} />
            <Route path="/enrichment" element={<Enrichment />} />
            <Route path="/requests" element={<Requests />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
