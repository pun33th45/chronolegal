import { useCallback, useRef, useState } from 'react'
import { useAuthStore } from '@/store/authStore'
import type { Citation, StreamChunk } from '@/types'

interface StreamingState {
  isStreaming: boolean
  streamedText: string
  citations: Citation[]
  error: string | null
  conversationId: string | null
}

export function useStreamingChat() {
  const { accessToken } = useAuthStore()
  const abortRef = useRef<AbortController | null>(null)
  const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

  const [state, setState] = useState<StreamingState>({
    isStreaming: false,
    streamedText: '',
    citations: [],
    error: null,
    conversationId: null,
  })

  const send = useCallback(
    async (
      message: string,
      conversationId: string | null,
      topK = 5,
      onTextChunk?: (chunk: string) => void,
      onDone?: (convId: string) => void,
    ) => {
      abortRef.current?.abort()
      abortRef.current = new AbortController()

      setState({ isStreaming: true, streamedText: '', citations: [], error: null, conversationId })

      try {
        const res = await fetch(`${BASE_URL}/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            conversation_id: conversationId,
            message,
            stream: true,
            top_k: topK,
          }),
          signal: abortRef.current.signal,
        })

        if (!res.ok) {
          const err = await res.json()
          throw new Error(err.detail ?? 'Stream request failed')
        }

        const reader = res.body!.getReader()
        const decoder = new TextDecoder()
        let accumulated = ''
        let resolvedConvId = conversationId

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const text = decoder.decode(value, { stream: true })
          for (const line of text.split('\n')) {
            if (!line.startsWith('data: ')) continue
            try {
              const chunk: StreamChunk = JSON.parse(line.slice(6))

              if (chunk.type === 'text' && chunk.content) {
                accumulated += chunk.content
                onTextChunk?.(chunk.content)
                setState((s) => ({ ...s, streamedText: accumulated }))
              } else if (chunk.type === 'citation' && chunk.citations) {
                setState((s) => ({ ...s, citations: chunk.citations! }))
              } else if (chunk.type === 'done') {
                if (chunk.conversation_id) resolvedConvId = chunk.conversation_id
                setState((s) => ({
                  ...s,
                  isStreaming: false,
                  conversationId: resolvedConvId,
                }))
                onDone?.(resolvedConvId ?? '')
              } else if (chunk.type === 'error') {
                throw new Error(chunk.error ?? 'Unknown stream error')
              }
            } catch {
              // Ignore malformed SSE lines
            }
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          setState((s) => ({ ...s, isStreaming: false, error: err.message }))
        }
      }
    },
    [accessToken, BASE_URL],
  )

  const abort = useCallback(() => {
    abortRef.current?.abort()
    setState((s) => ({ ...s, isStreaming: false }))
  }, [])

  return { ...state, send, abort }
}
