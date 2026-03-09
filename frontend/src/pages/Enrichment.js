import { useState } from "react";

export default function Enrichment() {
  const [domain,setDomain]=useState("");

  return (
    <div>
      <h2>Firmographic Enrichment Agent</h2>
      <p style={{color:"gray"}}>
        (Backend logic coming soon)
      </p>

      <input
        placeholder="Company Domain"
        value={domain}
        onChange={e=>setDomain(e.target.value)}
      />

      <button disabled style={{marginLeft:10}}>
        Enrich (Coming Soon)
      </button>
    </div>
  );
}
