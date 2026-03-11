import { useState } from "react";

export default function GoogleAgent() {
  return (
    <div className="bg-white rounded-2xl shadow-lg p-8 max-w-3xl">
      <h3 className="text-xl font-semibold mb-4">
        Google Discovery Agent
      </h3>

      <p className="text-gray-500 mb-4">
        Coming in Phase 2 – Web scraping + SERP enrichment
      </p>

      <button
        disabled
        className="bg-gray-400 text-white px-6 py-2 rounded-lg"
      >
        Coming Soon
      </button>
    </div>
  );
}

