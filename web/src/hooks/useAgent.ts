import { useState, useCallback, useEffect } from 'react'
import { Message, AgentResponse, InterruptInfo, ConfirmationInfo } from '../api/types'
import * as api from '../api/client'

interface UseAgentReturn {
  messages: Message[]
  isLoading: boolean
  error: string | null
  interrupt: InterruptInfo | null
  confirmation: ConfirmationInfo | null
  sessionId: string | null
  sendMessage: (content: string) => Promise<void>
  respondToInterrupt: (response: string) => Promise<void>
  respondToConfirmation: (confirmed: boolean) => Promise<void>
  clearChat: () => Promise<void>
}

export function useAgent(provider = 'openai'): UseAgentReturn {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [interrupt, setInterrupt] = useState<InterruptInfo | null>(null)
  const [confirmation, setConfirmation] = useState<ConfirmationInfo | null>(null)

  // initialize session on mount
  useEffect(() => {
    api.createSession(provider)
      .then(setSessionId)
      .catch(err => setError(err.message))
  }, [provider])

  const handleResponse = useCallback((response: AgentResponse) => {
    if (response.state === 'completed' && response.content) {
      const assistantMsg: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: response.content,
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, assistantMsg])
      setInterrupt(null)
      setConfirmation(null)
    } else if (response.state === 'interrupted' && response.interrupt) {
      setInterrupt(response.interrupt)
    } else if (response.state === 'awaiting_confirmation' && response.confirmation) {
      setConfirmation(response.confirmation)
    } else if (response.state === 'error') {
      setError(response.error || 'Unknown error')
    }
  }, [])

  const sendMessage = useCallback(async (content: string) => {
    if (!sessionId) return

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)
    setError(null)

    try {
      const response = await api.runAgent(sessionId, content)
      handleResponse(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message')
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, handleResponse])

  const respondToInterrupt = useCallback(async (response: string) => {
    if (!sessionId || !interrupt) return

    setIsLoading(true)
    try {
      const result = await api.resumeAgent(sessionId, interrupt.tool_call_id, response)
      handleResponse(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to respond')
    } finally {
      setIsLoading(false)
      setInterrupt(null)
    }
  }, [sessionId, interrupt, handleResponse])

  const respondToConfirmation = useCallback(async (confirmed: boolean) => {
    if (!sessionId || !confirmation) return

    setIsLoading(true)
    try {
      const result = await api.confirmOperation(sessionId, confirmation.tool_call_id, confirmed)
      handleResponse(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to confirm')
    } finally {
      setIsLoading(false)
      setConfirmation(null)
    }
  }, [sessionId, confirmation, handleResponse])

  const clearChat = useCallback(async () => {
    if (!sessionId) return
    try {
      await api.clearHistory(sessionId)
      setMessages([])
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear chat')
    }
  }, [sessionId])

  return {
    messages,
    isLoading,
    error,
    interrupt,
    confirmation,
    sessionId,
    sendMessage,
    respondToInterrupt,
    respondToConfirmation,
    clearChat,
  }
}
