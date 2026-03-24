import Button from "../ui/Button";
import Card from "../ui/Card";

function formatValue(value) {
  if (value == null || value === "") return "-";
  if (typeof value === "number") {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      maximumFractionDigits: 2,
    }).format(value);
  }
  return String(value);
}

export default function OptimizationModal({ isOpen, onClose, onConfirm, data, isLoading = false }) {
  if (!isOpen) return null;

  const acao = String(data?.acao || "").toUpperCase();
  const acaoLabel =
    acao === "ESCALAR"
      ? "Aumentar Verba"
      : acao === "PAUSAR"
      ? "Pausar Oferta"
      : acao === "AJUSTAR_DISPOSITIVO"
      ? "Ajustar Lance por Dispositivo"
      : acao === "AJUSTAR_HORARIO"
      ? "Ajustar Lance por Horário"
      : "Confirmar Otimizacao";
  const alvoLabel = acao === "AJUSTAR_DISPOSITIVO" ? "Dispositivo" : acao === "AJUSTAR_HORARIO" ? "Período" : "Servico";
  const alvoValor = data?.nome_servico || data?.dispositivo || "-";

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-900/50 p-4">
      <Card className="w-full max-w-lg">
        <div className="space-y-5">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Confirmar Otimizacao</h3>
            <p className="mt-1 text-sm text-slate-500">
              Revise os dados abaixo antes de autorizar a acao no Google/Meta Ads.
            </p>
            {data?.resumo ? <p className="mt-2 text-sm text-slate-700">{String(data.resumo)}</p> : null}
          </div>

          <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-slate-600">Acao</span>
              <span className="font-semibold text-slate-900">{acaoLabel}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-slate-600">{alvoLabel}</span>
              <span className="font-semibold text-slate-900">{alvoValor}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-slate-600">Mudanca</span>
              <span className="font-semibold text-slate-900">
                {formatValue(data?.valorAtual)} {" -> "} {formatValue(data?.valorNovo)}
              </span>
            </div>
          </div>

          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Esta acao tera impacto imediato nas APIs do Google/Meta Ads.
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onClose} disabled={isLoading}>
              Cancelar
            </Button>
            <Button type="button" variant="primary" onClick={onConfirm} isLoading={isLoading}>
              Confirmar Acao
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
