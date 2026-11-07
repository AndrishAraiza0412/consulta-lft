export type Citation = { article: string; text: string }

export type AskResponse = {
  status: 'answered' | 'no_answer'
  answer: string | null
  citations: Citation[]
  unverified_citations: string[]
  trace_id: string
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const UNREACHABLE = 'No se pudo conectar con el servidor. Inténtalo de nuevo.'
const UNEXPECTED = 'Ocurrió un error inesperado. Inténtalo de nuevo.'

export async function askQuestion(question: string): Promise<AskResponse> {
  let response: Response
  try {
    response = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    })
  } catch {
    throw new ApiError(0, UNREACHABLE)
  }
  if (response.ok) return response.json()

  const body = await response.json().catch(() => null)
  const detail = typeof body?.detail === 'string' ? body.detail : UNEXPECTED
  throw new ApiError(response.status, detail)
}
