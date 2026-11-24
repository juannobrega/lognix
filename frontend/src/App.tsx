import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from './auth/RequireAuth'
import { AppLayout } from './layout/AppLayout'
import { DashboardPage } from './pages/DashboardPage'
import { HostDetailPage } from './pages/HostDetailPage'
import { HostsPage } from './pages/HostsPage'
import { InsightsPage } from './pages/InsightsPage'
import { NewHostPage } from './pages/NewHostPage'
import { NotificationsPage } from './pages/NotificationsPage'
import { ProjectPage } from './pages/ProjectPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { LoginPage } from './pages/LoginPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { SettingsPage } from './pages/SettingsPage'
import { SetupPage } from './pages/SetupPage'
import { SystemPage } from './pages/SystemPage'
import { UsersPage } from './pages/UsersPage'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<SetupPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="hosts" element={<HostsPage />} />
          <Route path="hosts/new" element={<NewHostPage />} />
          <Route path="hosts/:id" element={<HostDetailPage />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="projects/:id" element={<ProjectPage />} />
          <Route path="insights" element={<InsightsPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="settings" element={<SettingsPage />}>
            <Route index element={<Navigate to="users" replace />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="ai" element={<PlaceholderPage title="IA" phase="0.9.0" />} />
            <Route path="usage" element={<PlaceholderPage title="Consumo de IA" phase="0.9.0" />} />
            <Route path="system" element={<SystemPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
