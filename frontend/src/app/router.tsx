import { createBrowserRouter } from 'react-router-dom'

import { LoginPage } from '../features/auth/components/login-page'
import { ProtectedRoute } from '../features/auth/protected-route'
import { ClinicsPage } from '../features/clinics/components/clinics-page'
import { AppShell } from '../shared/layout/app-shell'
import { HomePage } from './home-page'

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/cadastros/clinicas', element: <ClinicsPage /> },
    ],
  },
])
