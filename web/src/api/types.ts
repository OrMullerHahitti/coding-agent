export interface InterruptInfo {
  tool_name: string
  tool_call_id: string
  question: string
  context?: Record<string, unknown>
}

export interface ConfirmationInfo {
  tool_name: string
  tool_call_id: string
  message: string
  operation: string
  arguments: Record<string, unknown>
}

export interface AgentResponse {
  state: 'completed' | 'interrupted' | 'awaiting_confirmation' | 'error'
  content?: string
  interrupt?: InterruptInfo
  confirmation?: ConfirmationInfo
  error?: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
}

export interface WebSocketMessage {
  type: 'chunk' | 'reasoning' | 'tool_call' | 'interrupt' | 'confirmation' | 'done' | 'error'
  content?: string
  tool_name?: string
  tool_call_id?: string
  question?: string
  message?: string
  operation?: string
  arguments?: Record<string, unknown>
}
