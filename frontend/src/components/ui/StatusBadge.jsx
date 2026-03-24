const STATUS_STYLES = {
  RASCUNHO: "bg-amber-100 text-amber-800",
  APROVADA: "bg-blue-100 text-blue-800",
  ATIVA: "bg-green-100 text-green-800",
  PAUSADA: "bg-red-100 text-red-700",
  ERRO: "bg-orange-100 text-orange-800",
  ALTA: "bg-red-100 text-red-700",
  MEDIA: "bg-amber-100 text-amber-800",
  BAIXA: "bg-blue-100 text-blue-800",
};

export default function StatusBadge({ status }) {
  const label = (status || "RASCUNHO").toString().trim().toUpperCase();
  const classes = STATUS_STYLES[label] || "bg-slate-100 text-slate-700";

  return <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${classes}`}>{label}</span>;
}
