import { ConfirmationInfo } from '../api/types'

interface ConfirmationModalProps {
  confirmation: ConfirmationInfo
  onConfirm: () => void
  onReject: () => void
}

export function ConfirmationModal({ confirmation, onConfirm, onReject }: ConfirmationModalProps) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">
          Confirm Operation
        </h2>
        <p className="text-gray-600 mb-4">
          {confirmation.message}
        </p>
        <div className="text-sm text-gray-500 mb-4">
          <span className="font-medium">Tool:</span> {confirmation.tool_name}
          <br />
          <span className="font-medium">Operation:</span> {confirmation.operation}
        </div>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onReject}
            className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-white bg-red-600 rounded-lg hover:bg-red-700"
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}
