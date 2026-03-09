import { BrowserRouter, Routes, Route } from "react-router-dom";
import SalesNav from "./pages/SalesNav";
import Requests from "./pages/Requests";
import Sidebar from "./components/Sidebar";

export default function App() {
  return (
    <BrowserRouter>
      <div style={{display:"flex"}}>
        <Sidebar />
        <div style={{flex:1,padding:20}}>
          <Routes>
            <Route path="/" element={<SalesNav />} />
            <Route path="/requests" element={<Requests />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
