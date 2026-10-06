import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { Spinner } from '@/components/ui/Spinner'

// Pages
import LandingPage from '@/pages/LandingPage'
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import GoogleCallbackPage from '@/pages/GoogleCallbackPage'
import LegalPage from '@/pages/LegalPage'
import DashboardPage from '@/pages/DashboardPage'
import KnowledgeBasePage from '@/pages/KnowledgeBasePage'
import ChatPage from '@/pages/ChatPage'
import SearchPage from '@/pages/SearchPage'
import UploadPage from '@/pages/UploadPage'
import CaseViewerPage from '@/pages/CaseViewerPage'
import ComparePage from '@/pages/ComparePage'
import SettingsPage from '@/pages/SettingsPage'
import ProfilePage from '@/pages/ProfilePage'

// Layout
import AppLayout from '@/components/layout/AppLayout'

// Lazy-loaded: pull in the ~400KB recharts bundle (Analytics) or are rarely
// visited (Admin) — deferring them keeps that weight out of everyone else's
// initial load instead of shipping it on every login.
const AnalyticsPage = lazy(() => import('@/pages/AnalyticsPage'))
const AdminPage = lazy(() => import('@/pages/AdminPage'))

function PageFallback() {
  return (
    <div className="flex items-center justify-center h-full py-24">
      <Spinner />
    </div>
  )
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <>{children}</>
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<LandingPage />} />
          <Route
            path="/login"
            element={<PublicRoute><LoginPage /></PublicRoute>}
          />
          <Route
            path="/register"
            element={<PublicRoute><RegisterPage /></PublicRoute>}
          />
          <Route path="/auth/google/callback" element={<GoogleCallbackPage />} />
          <Route path="/privacy" element={<LegalPage kind="privacy" />} />
          <Route path="/terms" element={<LegalPage kind="terms" />} />

          {/* Protected routes with layout */}
          <Route
            path="/"
            element={<ProtectedRoute><AppLayout /></ProtectedRoute>}
          >
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="knowledge-base" element={<KnowledgeBasePage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="chat/:conversationId" element={<ChatPage />} />
            <Route path="search" element={<SearchPage />} />
            <Route path="compare" element={<ComparePage />} />
            <Route path="upload" element={<UploadPage />} />
            <Route
              path="analytics"
              element={<Suspense fallback={<PageFallback />}><AnalyticsPage /></Suspense>}
            />
            <Route path="cases/:caseId" element={<CaseViewerPage />} />
            <Route
              path="admin"
              element={<Suspense fallback={<PageFallback />}><AdminPage /></Suspense>}
            />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
