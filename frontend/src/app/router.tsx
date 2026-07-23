import { createBrowserRouter } from 'react-router-dom'

import { LoginPage } from '../features/auth/components/login-page'
import { ProtectedRoute } from '../features/auth/protected-route'
import { HomePage } from './home-page'

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <HomePage />
      </ProtectedRoute>
    ),
  },
])
