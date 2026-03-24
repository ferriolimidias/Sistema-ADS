import { useEffect, useState } from "react";

import Card from "../ui/Card";
import { authFetch } from "../../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function formatBRL(value) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0));
}

export default function AIPerformanceWidget() {
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState({
    economia_gerada_ia: 0,
    custo_total_ia: 0,
    roi_estimado_limpeza: 0,
  });

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setIsLoading(true);
        const response = await authFetch(`${API_BASE_URL}/admin/stats-ia?periodo_dias=30`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload?.detail || "Falha ao carregar stats de IA.");
        if (!mounted) return;
        setStats({
          economia_gerada_ia: Number(payload?.economia_gerada_ia || 0),
          custo_total_ia: Number(payload?.custo_total_ia || 0),
          roi_estimado_limpeza: Number(payload?.roi_estimado_limpeza || 0),
        });
      } catch (_error) {
        if (!mounted) return;
        setStats({ economia_gerada_ia: 0, custo_total_ia: 0, roi_estimado_limpeza: 0 });
      } finally {
        if (mounted) setIsLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, []);

  const roi = Number(stats.roi_estimado_limpeza || 0);
  const roiPrefix = roi >= 0 ? "+" : "-";

  return (
    <Card className="relative overflow-hidden border-slate-700 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 text-slate-100">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.15),transparent_55%)]" />
      <div className="relative">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">ROI do Funcionário Robô (30d)</p>
        <p className="mt-2 text-3xl font-extrabold md:text-5xl">
          {isLoading ? "..." : `${roiPrefix}${formatBRL(Math.abs(roi))}`}
        </p>
        <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-300 md:text-sm">
          <span>Economizado: {isLoading ? "..." : formatBRL(stats.economia_gerada_ia)}</span>
          <span>Custo Servidor IA: {isLoading ? "..." : formatBRL(stats.custo_total_ia)}</span>
        </div>
      </div>
    </Card>
  );
}
