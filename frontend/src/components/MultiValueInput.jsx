import { useState } from "react";

export default function MultiValueInput({ label, values, setValues, placeholder = "Type and press Enter" }) {
  const [input, setInput] = useState("");

  const addValue = (e) => {
    if (e.key === "Enter" && input.trim()) {
      e.preventDefault();

      if (!values.includes(input.trim())) {
        setValues([...values, input.trim()]);
      }

      setInput("");
    }
  };

  const removeValue = (index) => {
    const updated = [...values];
    updated.splice(index, 1);
    setValues(updated);
  };

  return (
    <div className="space-y-2">
      <label className="text-sm font-semibold text-slate-100">{label}</label>

      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={addValue}
        placeholder={placeholder}
        className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
      />

      <div className="flex flex-wrap gap-2">
        {values.map((v, i) => (
          <span
            key={i}
            onClick={() => removeValue(i)}
            className="cursor-pointer rounded-full border border-cyan-200/30 bg-cyan-300/15 px-3 py-1 text-sm text-cyan-100 transition hover:bg-cyan-300/25"
          >
            {v} ✕
          </span>
        ))}
      </div>
    </div>
  );
}
