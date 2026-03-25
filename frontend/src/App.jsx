import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import Navbar from "./components/layout/Navbar";
import { ToastProvider } from "./components/ui/ToastProvider";
import AprovacaoCampanha from "./pages/admin/AprovacaoCampanha";
import AuditLogs from "./pages/admin/AuditLogs";
import Clientes from "./pages/admin/Clientes";
import Configuracoes from "./pages/admin/Configuracoes";
import Dashboard from "./pages/admin/Dashboard";
import LimpezaTermos from "./pages/admin/LimpezaTermos";
import Perfil from "./pages/admin/Perfil";
import { getStoredAuth } from "./lib/auth";
import Login from "./pages/Login";
import NovaCampanha from "./pages/admin/NovaCampanha";
import ResetPassword from "./pages/ResetPassword";
import LandingPage from "./pages/public/LandingPage";

function ProtectedRoute({ children, allowRoles }) {
  const auth = getStoredAuth();
  const role = auth?.user?.role;
  const needsPasswordChange = Boolean(auth?.user?.needs_password_change);

  if (!auth?.user) {
    return <Navigate to="/login" replace />;
  }
  if (needsPasswordChange) {
    return <Navigate to="/redefinir-senha" replace />;
  }
  if (allowRoles && !allowRoles.includes(role)) {
    return <Navigate to={role === "CLIENTE" ? "/dashboard" : "/admin/dashboard"} replace />;
  }
  return children;
}

function HomeRedirect() {
  const auth = getStoredAuth();
  const role = auth?.user?.role;
  if (auth?.user?.needs_password_change) return <Navigate to="/redefinir-senha" replace />;
  if (role === "ADMIN") return <Navigate to="/admin/dashboard" replace />;
  if (role === "CLIENTE") return <Navigate to="/dashboard" replace />;
  return <Navigate to="/login" replace />;
}

function AuthenticatedPage({ children }) {
  return (
    <>
      <Navbar />
      {children}
    </>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/redefinir-senha" element={<ResetPassword />} />
          <Route path="/" element={<HomeRedirect />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute allowRoles={["CLIENTE"]}>
                <AuthenticatedPage>
                  <Dashboard />
                </AuthenticatedPage>
              </ProtectedRoute>
            }
          />
          <Route
            path="/perfil"
            element={
              <ProtectedRoute allowRoles={["ADMIN", "CLIENTE"]}>
                <AuthenticatedPage>
                  <Perfil />
                </AuthenticatedPage>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/perfil"
            element={
              <ProtectedRoute allowRoles={["ADMIN", "CLIENTE"]}>
                <AuthenticatedPage>
                  <Perfil />
                </AuthenticatedPage>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowRoles={["ADMIN"]}>
                <AuthenticatedPage>
                  <Dashboard />
                </AuthenticatedPage>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/dashboard"
            element={
              <ProtectedRoute allowRoles={["ADMIN"]}>
                <AuthenticatedPage>
                  <Dashboard />
                </AuthenticatedPage>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/clientes"
            element={
              <ProtectedRoute allowRoles={["ADMIN"]}>
                <AuthenticatedPage>
                  <Clientes />
                </AuthenticatedPage>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/configuracoes"
            element={
              <ProtectedRoute allowRoles={["ADMIN"]}>
                <AuthenticatedPage>
                  <Configuracoes />
                </AuthenticatedPage>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/logs"
            element={
              <ProtectedRoute allowRoles={["ADMIN"]}>
                <AuthenticatedPage>
                  <AuditLogs />
                </AuthenticatedPage>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/limpeza-termos"
            element={
              <ProtectedRoute allowRoles={["ADMIN"]}>
                <AuthenticatedPage>
                  <LimpezaTermos />
                </AuthenticatedPage>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/campanhas/nova"
            element={
              <ProtectedRoute allowRoles={["ADMIN"]}>
                <AuthenticatedPage>
                  <NovaCampanha />
                </AuthenticatedPage>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/campanhas/:campanha_id/aprovacao"
            element={
              <ProtectedRoute allowRoles={["ADMIN"]}>
                <AuthenticatedPage>
                  <AprovacaoCampanha />
                </AuthenticatedPage>
              </ProtectedRoute>
            }
          />
          <Route path="/oferta/:campanha_id/:nome_servico" element={<LandingPage />} />
          <Route path="*" element={<HomeRedirect />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
