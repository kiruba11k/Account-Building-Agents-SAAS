import { useEffect, useState } from "react";
import API from "../api";

export default function Requests(){
  const [data,setData]=useState([]);

  useEffect(()=>{
    const interval=setInterval(()=>{
      API.get("/api/requests").then(res=>setData(res.data));
    },5000);
    return ()=>clearInterval(interval);
  },[]);

  return(
    <div>
      <h2>Requests</h2>
      {data.map(r=>(
        <div key={r.id}>
          {r.request_name} - {r.status}
          {r.status==="Completed" && (
            <a href={`${process.env.REACT_APP_API_URL}/api/download/${r.id}`}>
              Download CSV
            </a>
          )}
        </div>
      ))}
    </div>
  );
}
