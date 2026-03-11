import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api";

export default function Results() {

  const { id } = useParams();

  const [status, setStatus] = useState({});
  const [results, setResults] = useState([]);

  const [page, setPage] = useState(1);
  const limit = 50;

  const loadStatus = async () => {

    const res = await api.get(`/api/request/${id}`);

    setStatus(res.data);

  };

  const loadResults = async (pageNumber) => {

    const res = await api.get(
      `/api/results/${id}?page=${pageNumber}&limit=${limit}`
    );

    setResults(res.data.results);

  };

  useEffect(() => {

    loadStatus();
    loadResults(page);

    const interval = setInterval(() => {

      loadStatus();
      loadResults(page);

    }, 5000);

    return () => clearInterval(interval);

  }, [page]);

  return (

    <div>

      <h2>Results</h2>

      <div>

        <p>Status: {status.phase}</p>

        <div style={{background:"#ddd",height:"10px"}}>

          <div
            style={{
              width:`${status.progress || 0}%`,
              background:"green",
              height:"10px"
            }}
          />

        </div>

      </div>

      <table border="1">

        <thead>

          <tr>
            <th>Company</th>
            <th>Domain</th>
            <th>Industry</th>
            <th>Employees</th>
            <th>Revenue</th>
          </tr>

        </thead>

        <tbody>

          {results.map((r,i)=>(

            <tr key={i}>

              <td>{r.name}</td>
              <td>{r.domain}</td>
              <td>{r.industry}</td>
              <td>{r.headcount}</td>
              <td>{r.revenue}</td>

            </tr>

          ))}

        </tbody>

      </table>

      <div style={{marginTop:"10px"}}>

        <button onClick={()=>setPage(page-1)} disabled={page===1}>
          Previous
        </button>

        <span style={{margin:"0 10px"}}>Page {page}</span>

        <button onClick={()=>setPage(page+1)}>
          Next
        </button>

      </div>

      <br/>

      <a href={`/api/download/${id}`}>Download CSV</a>

    </div>

  );

}
