import { useState } from "react";

import { authFetch } from "../../lib/auth";
import OptimizationModal from "../modals/OptimizationModal";
import { useToast } from "../ui/ToastProvider";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function formatBRL(value) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("pt-BR");
}

function roasBadgeClasses(roas) {
  const value = Number(roas || 0);
  if (value > 4) return "bg-emerald-100 text-emerald-700";
  if (value >= 2) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

export default function ServiceRankingTable({ data = [], onActionSuccess, enableActions = false }) {
  const toast = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [isProcessingAction, setIsProcessingAction] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);
  const rows = [...(Array.isArray(data) ? data : [])].sort(
    (a, b) => Number(b.roas || 0) - Number(a.roas || 0)
  );

  async function executarAcao(campanhaId, nomeServico, acao, valor = null) {
    if (!campanhaId) {
      throw new Error("Selecione uma campanha para executar a acao.");
    }
    const response = await authFetch(`${API_BASE_URL}/admin/otimizar-servico`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        campanha_id: Number(campanhaId),
        nome_servico: nomeServico,
        acao,
        valor,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload?.detail || "Falha ao executar acao de otimizacao.");
    }
    return payload;
  }

  function abrirModalAcao(payload) {
    setPendingAction(payload);
    setModalOpen(true);
  }

  function fecharModal() {
    if (isProcessingAction) return;
    setModalOpen(false);
    setPendingAction(null);
  }

  async function confirmarAcao() {
    if (!pendingAction) return;
    try {
      setIsProcessingAction(true);
      await executarAcao(
        pendingAction.campanha_id,
        pendingAction.nome_servico,
        pendingAction.acao,
        pendingAction.valor ?? null
      );
      toast.success("Acao executada com sucesso.");
      setModalOpen(false);
      setPendingAction(null);
      onActionSuccess?.();
    } catch (err) {
      toast.error(err?.message || "Falha ao executar acao de otimizacao.");
    } finally {
      setIsProcessingAction(false);
    }
  }

  return (
    <>
      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100 text-left text-xs uppercase tracking-wide text-slate-600">
            <tr>
              <th className="px-4 py-3">Servico</th>
              <th className="px-4 py-3">Gasto</th>
              <th className="px-4 py-3">Conversoes</th>
              <th className="px-4 py-3">CPA</th>
              <th className="px-4 py-3">ROAS</th>
              {enableActions ? <th className="px-4 py-3">Acoes</th> : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={`${row.nome_servico}-${idx}`} className="border-t border-slate-100">
                <td className="px-4 py-3 font-medium text-slate-800">{row.nome_servico || "Servico"}</td>
                <td className="px-4 py-3 text-slate-700">{formatBRL(row.gasto)}</td>
                <td className="px-4 py-3 text-slate-700">{formatNumber(row.conversoes)}</td>
                <td className="px-4 py-3 text-slate-700">
                  {row.cpa != null ? formatBRL(row.cpa) : "-"}
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${roasBadgeClasses(row.roas)}`}>
                    {row.roas != null ? `${Number(row.roas).toFixed(2)}x` : "N/A"}
                  </span>
                </td>
                {enableActions ? (
                  <td className="px-4 py-3">
                    {Number(row.roas || 0) < 2 ? (
                      <button
                        type="button"
                        onClick={() =>
                          abrirModalAcao({
                            campanha_id: row.campanha_id,
                            nome_servico: row.nome_servico || "Servico",
                            acao: "PAUSAR",
                            valor: null,
                            valorAtual: "ATIVA",
                            valorNovo: "PAUSADA",
                          })
                        }
                        className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700"
                      >
                        Pausar Oferta
                      </button>
                    ) : Number(row.roas || 0) > 4 ? (
                      <button
                        type="button"
                        onClick={() => {
                          const valorSugerido = Math.max(Number(row.gasto || 0) * 1.15, 5);
                          abrirModalAcao({
                            campanha_id: row.campanha_id,
                            nome_servico: row.nome_servico || "Servico",
                            acao: "ESCALAR",
                            valor: Number(valorSugerido.toFixed(2)),
                            valorAtual: Number(row.gasto || 0),
                            valorNovo: Number(valorSugerido.toFixed(2)),
                          });
                        }}
                        className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700"
                      >
                        Sugerir Aumento de Verba
                      </button>
                    ) : (
                      <span className="text-xs text-slate-400">-</span>
                    )}
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <OptimizationModal
        isOpen={modalOpen}
        onClose={fecharModal}
        onConfirm={confirmarAcao}
        data={pendingAction}
        isLoading={isProcessingAction}
      />
    </>
  );
}
