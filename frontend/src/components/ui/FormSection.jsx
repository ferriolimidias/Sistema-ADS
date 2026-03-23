export default function FormSection({ title, description, children, className = "" }) {
  return (
    <section className={className}>
      {title ? <h2 className="text-lg font-bold text-slate-900">{title}</h2> : null}
      {description ? <p className="mt-1 text-sm text-slate-500">{description}</p> : null}
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}
