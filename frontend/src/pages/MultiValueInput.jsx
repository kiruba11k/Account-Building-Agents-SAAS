import { useState } from "react";

export default function MultiValueInput({ label, values, setValues }) {

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

      <label className="font-semibold text-sm">
        {label}
      </label>

      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={addValue}
        placeholder="Type and press Enter"
        className="border px-3 py-2 rounded w-full"
      />

      <div className="flex flex-wrap gap-2">

        {values.map((v, i) => (

          <span
            key={i}
            onClick={() => removeValue(i)}
            className="bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-sm cursor-pointer"
          >
            {v} ✕
          </span>

        ))}

      </div>

    </div>

  );

}
