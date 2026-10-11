import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router";
import "./styles.css";
import { SessionProvider } from "./session.tsx";
import { AppLayout, PublicLayout } from "./components/Layouts.tsx";
import { Landing, PricingPage } from "./pages/Landing.tsx";
import { AuthPage } from "./pages/Auth.tsx";
import { AccountPage, AdminPage, DashboardPage } from "./pages/Dashboard.tsx";
import { ProjectPage, ProjectsPage } from "./pages/Multiplicador.tsx";
import { BatchPage } from "./pages/Batch.tsx";
import { ProductPage, ProductsPage } from "./pages/Products.tsx";
import { ScriptPage, ScriptsPage } from "./pages/Scripts.tsx";

function ScrollToTop() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (hash) document.querySelector(hash)?.scrollIntoView();
    else window.scrollTo(0, 0);
  }, [pathname, hash]);
  return null;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <SessionProvider>
        <ScrollToTop />
        <Routes>
          <Route element={<PublicLayout />}>
            <Route index element={<Landing />} />
            <Route path="planos" element={<PricingPage />} />
          </Route>
          <Route path="entrar" element={<AuthPage mode="login" />} />
          <Route path="criar-conta" element={<AuthPage mode="signup" />} />
          <Route path="app" element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="multiplicador" element={<ProjectsPage />} />
            <Route path="multiplicador/:id" element={<ProjectPage />} />
            <Route path="lotes/:id" element={<BatchPage />} />
            <Route path="produtos" element={<ProductsPage />} />
            <Route path="produtos/:id" element={<ProductPage />} />
            <Route path="roteiros" element={<ScriptsPage />} />
            <Route path="roteiros/:id" element={<ScriptPage />} />
            <Route path="conta" element={<AccountPage />} />
            <Route path="admin" element={<AdminPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </SessionProvider>
    </BrowserRouter>
  </StrictMode>,
);
