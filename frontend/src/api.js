import axios from "axios";

const API = axios.create({
  baseURL: "https://account-building-agents-saas-backend.onrender.com"
});

export default API;
