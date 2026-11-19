import { zodResolver } from '@hookform/resolvers/zod'
import { useState, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '../../../shared/ui/button'
import { Checkbox } from '../../../shared/ui/checkbox'
import { UserIcon } from '../../../shared/ui/icons'
import { PasswordField } from '../../../shared/ui/password-field'
import { TextField } from '../../../shared/ui/text-field'
import { SUPPORT_EMAIL } from '../../../shared/config/app-info'
import { ApiError } from '../api/auth-api'
import { useLoginMutation } from '../api/use-login-mutation'
import './login-form.css'

const loginSchema = z.object({
  login: z.string().trim().min(1, 'Informe seu usuário ou e-mail.'),
  password: z.string().min(1, 'Informe sua senha.'),
  rememberMe: z.boolean(),
})

type LoginFormValues = z.infer<typeof loginSchema>

function describeError(error: unknown): string | null {
  if (error === null || error === undefined) {
    return null
  }
  if (error instanceof ApiError) {
    return error.message
  }
  return 'Falha de conexão. Verifique sua internet e tente novamente.'
}

interface LoginFormProps {
  /** Aviso vindo de fora do formulário (ex.: "sessão expirada"), não é um erro de submit. */
  notice?: ReactNode
}

export function LoginForm({ notice }: LoginFormProps) {
  const [showForgotPasswordNotice, setShowForgotPasswordNotice] = useState(false)
  const mutation = useLoginMutation()
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { login: '', password: '', rememberMe: false },
  })

  const onSubmit = handleSubmit((values) => {
    mutation.mutate({
      login: values.login,
      password: values.password,
      rememberMe: values.rememberMe,
    })
  })

  const submitting = isSubmitting || mutation.isPending
  const errorMessage = describeError(mutation.error)

  return (
    <form className="login-form" onSubmit={onSubmit} noValidate>
      <p className="login-form__eyebrow">Acesso ao sistema</p>
      <h1 className="login-form__title">
        Bem-vindo
        <br />
        <em>de volta.</em>
      </h1>

      {notice && (
        <p role="status" className="login-form__notice">
          {notice}
        </p>
      )}

      <TextField
        id="login"
        label="Usuário"
        icon={<UserIcon />}
        autoComplete="username"
        disabled={submitting}
        errorMessage={errors.login?.message}
        {...register('login')}
      />

      <PasswordField
        id="password"
        label="Senha"
        autoComplete="current-password"
        disabled={submitting}
        errorMessage={errors.password?.message}
        {...register('password')}
      />

      <div className="login-form__row">
        <Checkbox label="Manter conectado" disabled={submitting} {...register('rememberMe')} />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => setShowForgotPasswordNotice((current) => !current)}
        >
          Esqueci a senha
        </Button>
      </div>

      {showForgotPasswordNotice && (
        <p role="status" className="login-form__notice">
          A recuperação de senha por conta própria ainda não está disponível — fale com o
          administrador do laboratório.
        </p>
      )}

      {errorMessage && (
        <p role="alert" className="login-form__domain-error">
          {errorMessage}
        </p>
      )}

      <Button type="submit" disabled={submitting}>
        {submitting ? 'Entrando…' : 'Entrar no sistema'}
      </Button>

      <p className="login-form__help">
        Problemas para acessar?{' '}
        <a className="login-form__help-link" href={`mailto:${SUPPORT_EMAIL}`}>
          Fale com o administrador.
        </a>
      </p>
    </form>
  )
}
