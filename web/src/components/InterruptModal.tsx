import { useState } from 'react'
import { InterruptInfo } from '../api/types'

interface InterruptModalProps {
  interrupt: InterruptInfo
  onRespond: (response: string) => void
}

export function InterruptModal({ interrupt, onRespond }: InterruptModalProps) {
  const [response, setResponse] = useState('')

  const handleSubmit = () => {
    if (response.trim()) {
      onRespond(response.trim())
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">
          Agent Question
        </h2>
        <p className="text-gray-700 mb-4">
          {interrupt.question}
        </p>
        <textarea
          value={response}
          onChange={e => setResponse(e.target.value)}
          placeholder="Your answer..."
          rows={3}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
          autoFocus
        />
        <div className="flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={!response.trim()}
            className="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            Submit
          </button>
        </div>
      </div>
    </div>
  )
}
