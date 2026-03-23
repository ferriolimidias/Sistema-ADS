import { useEffect, useMemo, useState } from "react";

import Card from "../../components/ui/Card";
import FormSection from "../../components/ui/FormSection";
import { Skeleton } from "../../components/ui/Skeleton";
import { useToast } from "../../components/ui/ToastProvider";
import { authFetch } from "../../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const ACOES = [
  { value: "", label: "Todas as Acoes" },
  { value: "LOGIN", label: "LOGIN" },
  { value: "LOGIN_FALHA", label: "LOGIN_FALHA" },
  { value: "CADASTRO_CLIENTE", label: "CADASTRO_CLIENTE" },
  { value: "ENVIO_WHATSAPP", label: "ENVIO_WHATSAPP" },
  { value: "ALTERAR_CONFIGURACOES", label: "ALTERAR_CONFIGURACOES" },
  { value: "DELETAR_CLIENTE", label: "DELETAR_CLIENTE" },
  { value: "NEGATIVAR_TERMO", label: "NEGATIVAR_TERMO" },
  { value: "CRIAR_CAMPANHA", label: "CRIAR_CAMPANHA" },
  { value: "ALTERAR_ORCAMENTO", label: "ALTERAR_ORCAMENTO" },
];

function formatarDataHora(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(date);
}

function getAcaoClasses(acao) {
  const key = String(acao || "").toUpperCase();
  if (key === "LOGIN_FALHA" || key === "DELETAR_CLIENTE") {
    return {
      row: "bg-red-50/50",
      badge: "bg-red-100 text-red-700",
    };
  }
  if (key === "ENVIO_WHATSAPP") {
    return {
      row: "bg-emerald-50/50",
      badge: "bg-emerald-100 text-emerald-700",
    };
  }
  if (key === "ALTERAR_CONFIGURACOES") {
    return {
      row: "bg-amber-50/50",
      badge: "bg-amber-100 text-amber-700",
    };
  }
  return {
    row: "",
    badge: "bg-slate-100 text-slate-700",
  };
}

export default function AuditLogs() {
  const toast = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [acaoFiltro, setAcaoFiltro] = useState("");
  const [logs, setLogs] = useState([]);

  async function carregarLogs(acao = "") {
    const query = acao ? `?acao=${encodeURIComponent(acao)}` : "";
    const response = await authFetch(`${API_BASE_URL}/admin/logs-atividade${query}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload?.detail || "Falha ao carregar logs.");
    setLogs(Array.isArray(payload) ? payload : []);
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setIsLoading(true);
        await carregarLogs(acaoFiltro);
      } catch (error) {
        console.error(error);
        if (mounted) toast.error(error?.message || "Erro ao carregar logs de atividade.");
      } finally {
        if (mounted) setIsLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [acaoFiltro]);

  const totalLabel = useMemo(() => `${logs.length} registro(s)`, [logs.length]);

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <Card>
          <FormSection
            title="Logs de Atividade"
            description="Rastreie acoes criticas de administradores e clientes no sistema."
          >
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div className="w-full max-w-xs space-y-1">
                <label className="block text-sm font-medium text-slate-700">Filtrar por Acao</label>
                <select
                  value={acaoFiltro}
                  onChange={(e) => setAcaoFiltro(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  {ACOES.map((acao) => (
                    <option key={acao.value || "ALL"} value={acao.value}>
                      {acao.label}
                    </option>
                  ))}
                </select>
              </div>
              <p className="text-sm text-slate-500">{totalLabel}</p>
            </div>
          </FormSection>
        </Card>

        <Card className="overflow-hidden">
          {isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 6 }).map((_, idx) => (
                <Skeleton key={idx} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-100 text-left text-xs uppercase tracking-wide text-slate-600">
                  <tr>
                    <th className="px-4 py-3">Data/Hora</th>
                    <th className="px-4 py-3">Usuario</th>
                    <th className="px-4 py-3">Acao</th>
                    <th className="px-4 py-3">Recurso</th>
                    <th className="px-4 py-3">IP</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                        Nenhum log encontrado para o filtro selecionado.
                      </td>
                    </tr>
                  ) : (
                    logs.map((log) => {
                      const classes = getAcaoClasses(log.acao);
                      return (
                      <tr key={log.id} className={`border-t border-slate-100 ${classes.row}`}>
                        <td className="px-4 py-3 text-slate-700">{formatarDataHora(log.timestamp)}</td>
                        <td className="px-4 py-3 text-slate-700">{log.usuario_email || `Usuario #${log.user_id || "-"}`}</td>
                        <td className="px-4 py-3">
                          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${classes.badge}`}>
                            {log.acao}
                          </span>
                        </td>
                        <td className="max-w-[340px] truncate px-4 py-3 text-slate-700" title={log.recurso}>
                          {log.recurso}
                        </td>
                        <td className="px-4 py-3 text-slate-600">{log.ip_address || "-"}</td>
                      </tr>
                    )})
                  )}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
