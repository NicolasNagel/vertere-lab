import { Link } from 'react-router-dom'

export function HomePage() {
  return (
    <main>
      <h1>Vertere Lab</h1>
      <p>Fundação do frontend — os módulos chegam por fatia vertical.</p>
      <nav>
        <Link to="/cadastros/clinicas">Clínicas parceiras</Link>
      </nav>
    </main>
  )
}
