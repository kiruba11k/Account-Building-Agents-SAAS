import { useMemo, useState } from "react";

export default function MultiSelectDropdown({ label, values, setValues, options = [], placeholder }) {
  const [query, setQuery] = useState("");

  const filteredOptions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return options;
    }
    return options.filter((option) => option.toLowerCase().includes(normalized));
  }, [options, query]);

  const toggleValue = (value) => {
    if (values.includes(value)) {
      setValues(values.filter((item) => item !== value));
      return;
    }
    setValues([...values, value]);
  };

  return (
    <div className="space-y-2">
      <label className="text-sm font-semibold text-slate-100">{label}</label>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder || "Type to filter options"}
        className="w-full rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-slate-100 placeholder:text-slate-300/70 focus:border-cyan-300/70 focus:outline-none"
      />

      <div className="max-h-44 space-y-1 overflow-y-auto rounded-xl border border-white/15 bg-white/5 p-2">
        {filteredOptions.length === 0 && (
          <p className="px-2 py-1 text-xs text-slate-300/70">No matching options</p>
        )}
        {filteredOptions.map((option) => (
          <label
            key={option}
            className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 text-sm text-slate-100 hover:bg-white/10"
          >
            <input
              type="checkbox"
              checked={values.includes(option)}
              onChange={() => toggleValue(option)}
              className="h-4 w-4 accent-cyan-400"
            />
            <span>{option}</span>
          </label>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {values.map((value) => (
          <button
            type="button"
            key={value}
            onClick={() => toggleValue(value)}
            className="rounded-full border border-cyan-200/30 bg-cyan-300/15 px-3 py-1 text-sm text-cyan-100 transition hover:bg-cyan-300/25"
          >
            {value} ✕
          </button>
        ))}
      </div>
    </div>
  );
}
