import { useRef, useEffect } from 'react'
import { useAgent } from './hooks/useAgent'
import { ChatMessage } from './components/ChatMessage'
import { ChatInput } from './components/ChatInput'
import { ConfirmationModal } from './components/ConfirmationModal'
import { InterruptModal } from './components/InterruptModal'

function App() {
  const {
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
  } = useAgent('openai')

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* header */}
      <header className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Coding Agent</h1>
        <div className="flex items-center gap-4">
          {sessionId && (
            <span className="text-sm text-gray-500">
              Session: {sessionId.slice(0, 8)}...
            </span>
          )}
          <button
            onClick={clearChat}
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            Clear Chat
          </button>
        </div>
      </header>

      {/* error banner */}
      {error && (
        <div className="bg-red-100 border-b border-red-200 px-4 py-2 text-red-700">
          {error}
        </div>
      )}

      {/* messages */}
      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 mt-20">
            <p className="text-lg mb-2">Welcome to Coding Agent</p>
            <p className="text-sm">Start a conversation by typing a message below</p>
          </div>
        ) : (
          messages.map(msg => <ChatMessage key={msg.id} message={msg} />)
        )}
        {isLoading && (
          <div className="flex justify-start mb-4">
            <div className="bg-gray-100 rounded-lg px-4 py-2 text-gray-500">
              Thinking...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* input */}
      <ChatInput
        onSend={sendMessage}
        disabled={isLoading || !sessionId}
        placeholder={!sessionId ? 'Connecting...' : 'Type a message...'}
      />

      {/* modals */}
      {confirmation && (
        <ConfirmationModal
          confirmation={confirmation}
          onConfirm={() => respondToConfirmation(true)}
          onReject={() => respondToConfirmation(false)}
        />
      )}
      {interrupt && (
        <InterruptModal
          interrupt={interrupt}
          onRespond={respondToInterrupt}
        />
      )}
    </div>
  )
}

export default App
