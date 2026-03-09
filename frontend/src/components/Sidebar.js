import { Link } from "react-router-dom";

export default function Sidebar() {
  return (
    <div style={{
      width:220,
      background:"#0f172a",
      color:"#fff",
      padding:20,
      minHeight:"100vh"
    }}>
      <h2 style={{marginBottom:20}}>LeadForge</h2>

      <Link to="/" style={link}> SalesNav Agent</Link>
      <Link to="/google" style={link}> Google Agent</Link>
      <Link to="/enrichment" style={link}> Enrichment Agent</Link>
      <Link to="/requests" style={link}> Requests</Link>
    </div>
  );
}

const link = {
  display:"block",
  color:"#fff",
  textDecoration:"none",
  marginBottom:15
};
