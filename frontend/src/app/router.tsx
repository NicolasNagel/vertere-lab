import { createBrowserRouter } from 'react-router-dom'

import { LoginPage } from '../features/auth/components/login-page'
import { ProtectedRoute } from '../features/auth/protected-route'
import { ExamFormPage } from '../features/catalog/components/exam-form-page'
import { ExamsPage } from '../features/catalog/components/exams-page'
import { ClinicsPage } from '../features/clinics/components/clinics-page'
import { PatientsPage } from '../features/patients/components/patients-page'
import { RolesPage } from '../features/roles/components/roles-page'
import { UsersPage } from '../features/users/components/users-page'
import { VeterinariansPage } from '../features/veterinarians/components/veterinarians-page'
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
      { path: '/cadastros/veterinarios', element: <VeterinariansPage /> },
      { path: '/pacientes', element: <PatientsPage /> },
      { path: '/cadastros/exames', element: <ExamsPage /> },
      { path: '/cadastros/exames/novo', element: <ExamFormPage /> },
      { path: '/cadastros/exames/:examId/editar', element: <ExamFormPage /> },
      { path: '/administracao/usuarios', element: <UsersPage /> },
      { path: '/administracao/perfis', element: <RolesPage /> },
    ],
  },
])
