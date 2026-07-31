import { createBrowserRouter } from 'react-router'

import { ProtectedRoute } from '../features/auth/protected-route'
import { AppShell } from '../shared/layout/app-shell'

export const router = createBrowserRouter([
  {
    path: '/login',
    lazy: async () => ({
      Component: (await import('../features/auth/components/login-page')).LoginPage,
    }),
  },
  {
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      {
        path: '/',
        lazy: async () => ({ Component: (await import('./home-page')).HomePage }),
      },
      {
        path: '/operacao',
        lazy: async () => ({
          Component: (await import('../features/attendances/components/attendance-list-page'))
            .AttendanceListPage,
        }),
      },
      {
        path: '/operacao/novo',
        lazy: async () => ({
          Component: (await import('../features/attendances/components/attendance-draft-page'))
            .AttendanceDraftPage,
        }),
      },
      {
        path: '/operacao/:attendanceId',
        lazy: async () => ({
          Component: (await import('../features/attendances/components/attendance-detail-page'))
            .AttendanceDetailPage,
        }),
      },
      {
        path: '/cadastros/clinicas',
        lazy: async () => ({
          Component: (await import('../features/clinics/components/clinics-page')).ClinicsPage,
        }),
      },
      {
        path: '/cadastros/veterinarios',
        lazy: async () => ({
          Component: (await import('../features/veterinarians/components/veterinarians-page'))
            .VeterinariansPage,
        }),
      },
      {
        path: '/pacientes',
        lazy: async () => ({
          Component: (await import('../features/patients/components/patients-page')).PatientsPage,
        }),
      },
      {
        path: '/cadastros/exames',
        lazy: async () => ({
          Component: (await import('../features/catalog/components/exams-page')).ExamsPage,
        }),
      },
      {
        path: '/cadastros/exames/novo',
        lazy: async () => ({
          Component: (await import('../features/catalog/components/exam-form-page')).ExamFormPage,
        }),
      },
      {
        path: '/cadastros/exames/:examId/editar',
        lazy: async () => ({
          Component: (await import('../features/catalog/components/exam-form-page')).ExamFormPage,
        }),
      },
      {
        path: '/administracao/usuarios',
        lazy: async () => ({
          Component: (await import('../features/users/components/users-page')).UsersPage,
        }),
      },
      {
        path: '/administracao/perfis',
        lazy: async () => ({
          Component: (await import('../features/roles/components/roles-page')).RolesPage,
        }),
      },
      {
        path: '/financeiro/fechamentos',
        lazy: async () => ({
          Component: (await import('../features/billing/components/closures-list-page'))
            .ClosuresListPage,
        }),
      },
      {
        path: '/financeiro/fechamento',
        lazy: async () => ({
          Component: (await import('../features/billing/components/closure-preview-page'))
            .ClosurePreviewPage,
        }),
      },
      {
        path: '/financeiro/fechamentos/:closureId',
        lazy: async () => ({
          Component: (await import('../features/billing/components/closure-detail-page'))
            .ClosureDetailPage,
        }),
      },
    ],
  },
])
