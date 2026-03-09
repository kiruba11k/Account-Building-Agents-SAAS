import { useState } from "react";
import API from "../api";

export default function SalesNav() {
  const [name,setName]=useState("");

  const launch=async()=>{
    await API.post("/api/run-salesnav",{request_name:name});
    alert("Launched!");
  };

  return (
    <div>
      <h2>SalesNav Agent</h2>
      <input placeholder="Request Name"
        value={name}
        onChange={e=>setName(e.target.value)}
      />
      <button onClick={launch}>Launch</button>
    </div>
  );
}
