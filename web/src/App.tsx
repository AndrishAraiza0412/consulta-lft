import { type FormEvent, useState } from 'react'
import { ApiError, askQuestion, type AskResponse } from './api'
import './App.css'

function Result({ result }: { result: AskResponse }) {
  if (result.status === 'no_answer') {
    return (
      <p className="no-answer">
        No encontré la respuesta en la Ley Federal del Trabajo. Prueba a reformular tu pregunta.
      </p>
    )
  }
  return (
    <>
      <p className="answer">{result.answer}</p>
      {result.unverified_citations.length > 0 && (
        <p className="warning">
          Estas citas no se pudieron verificar: {result.unverified_citations.join(', ')}. Compruébalas
          antes de confiar en ellas.
        </p>
      )}
      <h2>Artículos citados</h2>
      {result.citations.map((citation) => (
        <details key={citation.article}>
          <summary>Artículo {citation.article}</summary>
          <p className="article-text">{citation.text}</p>
        </details>
      ))}
    </>
  )
}

export default function App() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AskResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || loading) return
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      setResult(await askQuestion(trimmed))
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Ocurrió un error inesperado.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <header>
        <h1>Consulta LFT</h1>
        <p>Pregunta sobre la Ley Federal del Trabajo. Cada respuesta cita sus artículos.</p>
      </header>

      <form onSubmit={submit}>
        <label htmlFor="question">Tu pregunta</label>
        <textarea
          id="question"
          value={question}
          maxLength={500}
          rows={3}
          placeholder="¿Cuántos días de vacaciones me corresponden el primer año?"
          onChange={(event) => setQuestion(event.target.value)}
        />
        <div className="form-footer">
          <span className="counter">{question.length} / 500</span>
          <button type="submit" disabled={loading}>
            {loading ? 'Buscando…' : 'Preguntar'}
          </button>
        </div>
      </form>

      <section aria-live="polite" className="result">
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {result && <Result result={result} />}
      </section>

      <footer>Herramienta informativa. No es asesoría legal.</footer>
    </main>
  )
}
