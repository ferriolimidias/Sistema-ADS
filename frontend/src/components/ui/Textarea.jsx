export default function Textarea({ label, error, id, className = "", ...props }) {
  const textareaId = id || props.name;

  return (
    <div className="w-full">
      {label ? (
        <label htmlFor={textareaId} className="mb-1 block text-sm font-medium text-slate-700">
          {label}
        </label>
      ) : null}

      <textarea
        id={textareaId}
        className={[
          "w-full rounded-md border px-3 py-2",
          "focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500",
          "disabled:bg-gray-100 disabled:text-slate-500",
          error ? "border-red-500" : "border-gray-300",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
        {...props}
      />

      {error ? <p className="mt-1 text-xs text-red-600">{error}</p> : null}
    </div>
  );
}
