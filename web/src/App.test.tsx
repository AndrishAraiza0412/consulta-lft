import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

const QUESTION = '¿Cuántos días de vacaciones?'

function mockResponse(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  )
}

const answered = {
  status: 'answered',
  answer: 'Son doce días [Art. 76].',
  citations: [{ article: '76', text: 'Texto completo del artículo.' }],
  unverified_citations: [],
  trace_id: 'abc',
}

async function submit(question = QUESTION) {
  const user = userEvent.setup()
  render(<App />)
  await user.type(screen.getByLabelText(/tu pregunta/i), question)
  await user.click(screen.getByRole('button', { name: /preguntar/i }))
  return user
}

afterEach(() => vi.unstubAllGlobals())

test('sends the question to the API', async () => {
  mockResponse(200, answered)
  await submit()
  await screen.findByText(answered.answer)
  const [url, init] = vi.mocked(fetch).mock.calls[0]
  expect(url).toBe('/ask')
  expect(JSON.parse(init?.body as string)).toEqual({ question: QUESTION })
})

test('shows the answer and a citation that opens its article text', async () => {
  mockResponse(200, answered)
  const user = await submit()
  await screen.findByText(answered.answer)
  const text = screen.getByText('Texto completo del artículo.')
  expect(text).not.toBeVisible()
  await user.click(screen.getByText('Artículo 76'))
  expect(text).toBeVisible()
})

test('shows the no-answer message for no_answer', async () => {
  mockResponse(200, { ...answered, status: 'no_answer', answer: null, citations: [] })
  await submit()
  expect(await screen.findByText(/no encontré la respuesta/i)).toBeInTheDocument()
})

test('warns about unverified citations', async () => {
  mockResponse(200, { ...answered, unverified_citations: ['999'] })
  await submit()
  expect(await screen.findByText(/no se pudieron verificar/i)).toHaveTextContent('999')
})

test.each([429, 503])('shows the server message on %i', async (status) => {
  mockResponse(status, { detail: 'Mensaje del servidor.' })
  await submit()
  expect(await screen.findByRole('alert')).toHaveTextContent('Mensaje del servidor.')
})

test('shows a generic message when the server is unreachable', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('failed') }))
  await submit()
  expect(await screen.findByRole('alert')).toHaveTextContent(/no se pudo conectar/i)
})

test('disables submit while loading and keeps the typed question after an error', async () => {
  let finish: (response: Response) => void = () => {}
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => { finish = resolve })))
  await submit()
  const button = screen.getByRole('button', { name: /buscando/i })
  expect(button).toBeDisabled()
  finish(new Response(JSON.stringify({ detail: 'Falla.' }), { status: 503 }))
  await screen.findByRole('alert')
  expect(screen.getByLabelText(/tu pregunta/i)).toHaveValue(QUESTION)
  await waitFor(() => expect(screen.getByRole('button', { name: /preguntar/i })).toBeEnabled())
})

test('does not submit an empty question', async () => {
  vi.stubGlobal('fetch', vi.fn())
  await submit('   ')
  expect(fetch).not.toHaveBeenCalled()
})

test('enforces the 500-character limit in the input', () => {
  render(<App />)
  expect(screen.getByLabelText(/tu pregunta/i)).toHaveAttribute('maxlength', '500')
})

test('always shows the legal notice', () => {
  render(<App />)
  expect(screen.getByText('Herramienta informativa. No es asesoría legal.')).toBeInTheDocument()
})
