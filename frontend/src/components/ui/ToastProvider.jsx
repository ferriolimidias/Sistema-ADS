import { createContext, useContext, useMemo, useState } from "react";

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const remove = (id) => setToasts((prev) => prev.filter((item) => item.id !== id));

  const show = (type, message, duration = 3200) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    window.setTimeout(() => remove(id), duration);
  };

  const api = useMemo(
    () => ({
      show: (message) => show("info", message),
      info: (message) => show("info", message),
      success: (message) => show("success", message),
      warning: (message) => show("warning", message),
      error: (message) => show("error", message),
      promise: async (promise, messages = {}) => {
        const {
          loading = "Processando...",
          success = "Concluido com sucesso.",
          error = "Falha na operacao.",
        } = messages;
        const loadingId = `${Date.now()}-${Math.random()}`;
        setToasts((prev) => [...prev, { id: loadingId, type: "info", message: loading }]);
        try {
          const result = await promise;
          remove(loadingId);
          show("success", success);
          return result;
        } catch (err) {
          remove(loadingId);
          show("error", typeof error === "function" ? error(err) : error);
          throw err;
        }
      },
      dismiss: remove,
    }),
    []
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="fixed right-4 top-4 z-50 space-y-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`rounded-lg px-4 py-3 text-sm font-medium shadow-lg ${
              toast.type === "success"
                ? "bg-emerald-600 text-white"
                : toast.type === "warning"
                ? "bg-amber-500 text-slate-900"
                : toast.type === "error"
                ? "bg-red-600 text-white"
                : "bg-slate-800 text-white"
            }`}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast deve ser usado dentro de ToastProvider.");
  }
  return context;
}
