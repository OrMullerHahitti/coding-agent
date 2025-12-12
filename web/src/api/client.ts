import { AgentResponse } from './types'

const API_BASE = '/api'

export async function createSession(provider = 'openai'): Promise<string> {
  const response = await fetch(`${API_BASE}/sessions?provider=${provider}`, {
    method: 'POST',
  })
  if (!response.ok) throw new Error('Failed to create session')
  const data = await response.json()
  return data.session_id
}

export async function runAgent(sessionId: string, message: string): Promise<AgentResponse> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, stream: false }),
  })
  if (!response.ok) throw new Error('Failed to run agent')
  return response.json()
}

export async function resumeAgent(
  sessionId: string,
  toolCallId: string,
  userResponse: string
): Promise<AgentResponse> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool_call_id: toolCallId, response: userResponse }),
  })
  if (!response.ok) throw new Error('Failed to resume agent')
  return response.json()
}

export async function confirmOperation(
  sessionId: string,
  toolCallId: string,
  confirmed: boolean
): Promise<AgentResponse> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool_call_id: toolCallId, confirmed }),
  })
  if (!response.ok) throw new Error('Failed to confirm operation')
  return response.json()
}

export async function clearHistory(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/clear`, {
    method: 'POST',
  })
  if (!response.ok) throw new Error('Failed to clear history')
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
  })
  if (!response.ok) throw new Error('Failed to delete session')
}
