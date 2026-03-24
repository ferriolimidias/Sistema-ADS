const DAYS_ORDER = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"];

const DAY_LABELS = {
  MONDAY: "Segunda",
  TUESDAY: "Terca",
  WEDNESDAY: "Quarta",
  THURSDAY: "Quinta",
  FRIDAY: "Sexta",
  SATURDAY: "Sabado",
  SUNDAY: "Domingo",
};

function formatBRL(value) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0));
}

export default function DaypartingHeatmap({ data = [] }) {
  const normalized = Array.isArray(data) ? data : [];
  const byKey = new Map();

  let totalCost = 0;
  let totalConversions = 0;
  let maxConversions = 0;

  for (const row of normalized) {
    const day = String(row?.day_of_week || "").toUpperCase();
    const hour = Number(row?.hour_of_day ?? -1);
    if (!DAYS_ORDER.includes(day) || hour < 0 || hour > 23) continue;

    const key = `${day}:${hour}`;
    const current = byKey.get(key) || { conversions: 0, cost: 0 };
    const conversions = Number(row?.conversions || 0);
    const cost = Number(row?.cost || 0);
    current.conversions += conversions;
    current.cost += cost;
    byKey.set(key, current);

    totalCost += cost;
    totalConversions += conversions;
    if (current.conversions > maxConversions) maxConversions = current.conversions;
  }

  const mediaCpa = totalConversions > 0 ? totalCost / totalConversions : 0;

  function cellStyle(conversions, cost) {
    if (conversions > 0) {
      const ratio = maxConversions > 0 ? Math.min(1, conversions / maxConversions) : 0;
      const alpha = 0.2 + ratio * 0.7;
      return { backgroundColor: `rgba(22, 163, 74, ${alpha.toFixed(3)})` };
    }
    if (conversions === 0 && cost > mediaCpa && cost > 0) {
      const overflow = mediaCpa > 0 ? Math.min(1, (cost - mediaCpa) / mediaCpa) : 0.5;
      const alpha = 0.18 + overflow * 0.62;
      return { backgroundColor: `rgba(239, 68, 68, ${alpha.toFixed(3)})` };
    }
    return { backgroundColor: "rgba(226, 232, 240, 0.8)" };
  }

  return (
    <div className="w-full overflow-x-auto">
      <div className="min-w-[980px]">
        <div className="grid grid-cols-[auto_repeat(24,_minmax(0,_1fr))] gap-1">
          <div className="sticky left-0 z-10 bg-white p-1 text-xs font-semibold text-slate-600">Dia/Hora</div>
          {Array.from({ length: 24 }).map((_, h) => (
            <div key={`head-${h}`} className="p-1 text-center text-[10px] font-semibold text-slate-500">
              {String(h).padStart(2, "0")}h
            </div>
          ))}

          {DAYS_ORDER.map((day) => (
            <div key={day} className="contents">
              <div className="sticky left-0 z-10 flex items-center bg-white p-1 text-xs font-semibold text-slate-700">
                {DAY_LABELS[day]}
              </div>
              {Array.from({ length: 24 }).map((_, h) => {
                const key = `${day}:${h}`;
                const cell = byKey.get(key) || { conversions: 0, cost: 0 };
                const conversions = Number(cell.conversions || 0);
                const cost = Number(cell.cost || 0);
                return (
                  <div
                    key={key}
                    className="h-6 rounded-sm border border-white/40 transition hover:opacity-90"
                    style={cellStyle(conversions, cost)}
                    title={`${DAY_LABELS[day]} - ${String(h).padStart(2, "0")}h: ${conversions.toFixed(
                      2
                    )} Conversoes / Gasto: ${formatBRL(cost)}`}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
