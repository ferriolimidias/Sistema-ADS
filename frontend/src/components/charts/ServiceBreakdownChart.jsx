import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function formatBRL(value) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

export default function ServiceBreakdownChart({ data = [] }) {
  const chartData = (Array.isArray(data) ? data : []).map((item) => ({
    nome_servico: item.nome_servico || "Servico",
    gasto: Number(item.gasto || 0),
    roas: Number(item.roas || 0),
  }));

  return (
    <div className="h-[340px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 8, right: 16, left: 4, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="nome_servico" tick={{ fill: "#475569", fontSize: 12 }} />
          <YAxis yAxisId="left" tick={{ fill: "#475569", fontSize: 12 }} tickFormatter={(value) => `R$ ${Number(value || 0).toFixed(0)}`} />
          <YAxis yAxisId="right" orientation="right" tick={{ fill: "#475569", fontSize: 12 }} tickFormatter={(value) => `${Number(value || 0).toFixed(1)}x`} />
          <Tooltip
            formatter={(value, name) => {
              if (name === "gasto") return [formatBRL(value), "Gasto"];
              if (name === "roas") return [`${Number(value || 0).toFixed(2)}x`, "ROAS"];
              return [value, name];
            }}
            labelFormatter={(label) => `Servico: ${label}`}
          />
          <Legend
            formatter={(value) => (value === "gasto" ? "Gasto (R$)" : value === "roas" ? "ROAS" : value)}
          />
          <Bar yAxisId="left" dataKey="gasto" fill="#2563eb" radius={[8, 8, 0, 0]} />
          <Line yAxisId="right" type="monotone" dataKey="roas" stroke="#16a34a" strokeWidth={2.5} dot={{ r: 3 }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
