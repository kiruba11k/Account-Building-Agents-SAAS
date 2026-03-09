import { useState } from "react";

export default function GoogleAgent() {
  const [industry,setIndustry]=useState("");

  return (
    <div>
      <h2>Google Discovery Agent</h2>
      <p style={{color:"gray"}}>
        (Backend logic coming soon)
      </p>

      <input
        placeholder="Industry Include"
        value={industry}
        onChange={e=>setIndustry(e.target.value)}
      />

      <button disabled style={{marginLeft:10}}>
        Launch (Coming Soon)
      </button>
    </div>
  );
}
