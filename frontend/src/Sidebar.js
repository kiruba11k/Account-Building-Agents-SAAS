import { Link } from "react-router-dom";

export default function Sidebar() {
  return (
    <div style={{width:200,background:"#111",color:"#fff",padding:20}}>
      <h3>LeadForge</h3>
      <Link to="/" style={{display:"block",color:"#fff"}}>SalesNav</Link>
      <Link to="/requests" style={{display:"block",color:"#fff"}}>Requests</Link>
    </div>
  );
}
