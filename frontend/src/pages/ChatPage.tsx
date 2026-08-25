import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Bot,
  CheckCircle2,
  ChevronRight,
  Copy,
  Loader2,
  Plus,
  Send,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  User,
  X,
} from 'lucide-react'
import { chatApi, feedbackApi } from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/utils/cn'
import { CitationCard } from '@/components/chat/CitationCard'
import type { Citation, Message } from '@/types'

const SUGGESTED = [
  'Explain Article 21 of the Indian Constitution.',
  'What is the doctrine of basic structure?',
  'Landmark cases on free speech in India.',
]

// Real pipeline stages, driven by actual backend signals (not fabricated):
// "question" the instant a message is sent, "retrieval"/"reranking" from
// SSE "status" events emitted by RAGPipeline.stream() at those exact points,
// "answer" once the "citation" event arrives (citations are only sent after
// reranking + the evidence-threshold gate pass, strictly before any text).
type PipelineStage = 'question' | 'retrieving' | 'reranking' | 'answering' | null
const PIPELINE_STEPS: { key: Exclude<PipelineStage, null>; label: string }[] = [
  { key: 'question', label: 'Question' },
  { key: 'retrieving', label: 'Retrieval' },
  { key: 'reranking', label: 'Reranking' },
  { key: 'answering', label: 'Answer' },
]

export default function ChatPage() {
  const { conversationId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { accessToken } = useAuthStore()

  const [input, setInput] = useState(searchParams.get('q') || '')
  const [streamingText, setStreamingText] = useState('')
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null)
  const [activeConvId, setActiveConvId] = useState<string | null>(conversationId || null)
  const [pipelineStage, setPipelineStage] = useState<PipelineStage>(null)

  const [scopedCase, setScopedCase] = useState<{ id: string; name: string } | null>(() => {
    const id = searchParams.get('case')
    const name = searchParams.get('name')
    return id && name ? { id, name } : null
  })

  // RAG_REQUEST_TIMEOUT_MS: the backend's own real, measured round trip
  // (query rewrite -> embed -> Chroma retrieve -> rerank -> Groq generate)
  // is ~20-25s under normal conditions. This bounds the wait generously
  // above that rather than tuning it tightly, since the fetch() below
  // previously had no timeout at all -- if the backend ever stalls (e.g.
  // a stuck embedded-Chroma call), the UI would show "Searching legal
  // corpus..." forever with no way to recover short of a page reload.
  const RAG_REQUEST_TIMEOUT_MS = 90_000

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Conversations list
  const { data: conversations } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => chatApi.getConversations(),
  })

  // Messages for active conversation
  const { data: activeConv, refetch: refetchConv } = useQuery({
    queryKey: ['conversation', activeConvId],
    queryFn: () => chatApi.getConversation(activeConvId!),
    enabled: !!activeConvId,
  })

  const messages = useMemo(() => activeConv?.messages || [], [activeConv])

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  // Auto-fill from URL param
  useEffect(() => {
    const q = searchParams.get('q')
    if (q && !activeConvId) {
      setInput(q)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [searchParams, activeConvId])

  async function sendMessage(messageOverride?: string) {
    const userMessage = (messageOverride ?? input).trim()
    if (!userMessage || isStreaming) return
    if (!messageOverride) setInput('')
    setIsStreaming(true)
    setStreamingText('')
    setStreamingCitations([])
    setChatError(null)
    setLastFailedMessage(null)
    setPipelineStage('question')

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), RAG_REQUEST_TIMEOUT_MS)
    let sawAnyChunk = false

    try {
      const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
      const response = await fetch(`${BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          conversation_id: activeConvId,
          message: userMessage,
          stream: true,
          top_k: 5,
          include_related_cases: true,
          filters: scopedCase ? { case_id: scopedCase.id } : undefined,
        }),
        signal: controller.signal,
      })

      if (!response.ok) {
        let detail = `Request failed (HTTP ${response.status})`
        try {
          const body = await response.json()
          detail = body.detail ?? detail
        } catch {
          // response body wasn't JSON; keep the generic status-based message
        }
        throw new Error(detail)
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let convId = activeConvId

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value)
        const lines = text.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const chunk = JSON.parse(line.slice(6))
            sawAnyChunk = true
            if (chunk.type === 'status') {
              if (chunk.content === 'retrieving') setPipelineStage('retrieving')
              else if (chunk.content === 'reranking') setPipelineStage('reranking')
            } else if (chunk.type === 'text') {
              setPipelineStage('answering')
              setStreamingText((prev) => prev + (chunk.content || ''))
            } else if (chunk.type === 'citation') {
              setPipelineStage('answering')
              setStreamingCitations(chunk.citations || [])
            } else if (chunk.type === 'done') {
              if (chunk.conversation_id) convId = chunk.conversation_id
            } else if (chunk.type === 'error') {
              throw new Error(chunk.error || 'The assistant reported an error generating a response.')
            }
          } catch (parseErr) {
            if (parseErr instanceof Error && parseErr.message.startsWith('The assistant')) {
              throw parseErr
            }
            // Otherwise: a malformed SSE line — ignore and keep reading.
          }
        }
      }

      if (convId && convId !== activeConvId) {
        setActiveConvId(convId)
        navigate(`/chat/${convId}`, { replace: true })
      }

      await qc.invalidateQueries({ queryKey: ['conversations'] })
      await refetchConv()
    } catch (err) {
      const timedOut = controller.signal.aborted && !sawAnyChunk
      const message = timedOut
        ? "This is taking longer than expected and was cancelled. The backend may be under load — please try again."
        : err instanceof Error
          ? err.message
          : 'Something went wrong while generating a response.'
      console.error('Chat request failed:', err)
      setChatError(message)
      setLastFailedMessage(userMessage)
    } finally {
      clearTimeout(timeoutId)
      setIsStreaming(false)
      setStreamingText('')
      setStreamingCitations([])
      setPipelineStage(null)
    }
  }

  async function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      await sendMessage()
    }
  }

  async function deleteConversation(id: string) {
    await chatApi.deleteConversation(id)
    if (id === activeConvId) {
      setActiveConvId(null)
      navigate('/chat')
    }
    qc.invalidateQueries({ queryKey: ['conversations'] })
  }

  return (
    <div className="flex h-full">
      {/* Sidebar: conversation history */}
      <aside className="w-64 border-r border-border flex flex-col bg-card/30">
        <div className="p-3 border-b border-border">
          <button
            onClick={() => { setActiveConvId(null); navigate('/chat') }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/10 text-primary text-sm font-medium hover:bg-primary/20 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Conversation
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations?.map((conv) => (
            <div
              key={conv.id}
              className={cn(
                'group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer text-sm transition-colors',
                conv.id === activeConvId
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground',
              )}
              onClick={() => {
                setActiveConvId(conv.id)
                navigate(`/chat/${conv.id}`)
              }}
            >
              <Bot className="w-3.5 h-3.5 flex-shrink-0" />
              <span className="flex-1 truncate text-xs">{conv.title}</span>
              <button
                onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id) }}
                className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* Chat main */}
      <div className="flex-1 flex flex-col">
        {scopedCase && (
          <div className="flex items-center justify-between gap-3 px-4 py-2 border-b border-primary/20 bg-primary/5 text-sm">
            <span className="text-primary">
              Researching: <span className="font-medium">{scopedCase.name}</span>
            </span>
            <button
              onClick={() => {
                setScopedCase(null)
                navigate('/chat', { replace: true })
              }}
              className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-xs"
            >
              <X className="w-3.5 h-3.5" />
              Clear
            </button>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {!activeConvId && messages.length === 0 && !isStreaming && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                <Bot className="w-8 h-8 text-primary" />
              </div>
              <h2 className="text-xl font-semibold text-foreground mb-2">ChronoLegal AI</h2>
              <p className="text-muted-foreground mb-8 max-w-sm">
                {scopedCase
                  ? `Ask a question about ${scopedCase.name}. I'll search its indexed passages and give you a grounded, cited answer.`
                  : "Ask any legal question. I'll search the indexed judgments and give you grounded, cited answers."}
              </p>
              <div className="space-y-2 w-full max-w-md">
                {SUGGESTED.map((p) => (
                  <button
                    key={p}
                    onClick={() => setInput(p)}
                    className="w-full text-left px-4 py-3 rounded-xl border border-border hover:border-primary/30 hover:bg-primary/5 text-sm text-muted-foreground hover:text-foreground transition-all"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}

          {/* Streaming message */}
          {isStreaming && (
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-primary" />
              </div>
              <div className="flex-1">
                {streamingText ? (
                  <div className="legal-prose">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {streamingText}
                    </ReactMarkdown>
                    <span className="typing-cursor" />
                  </div>
                ) : (
                  <PipelineIndicator stage={pipelineStage} />
                )}
                {streamingCitations.length > 0 && (
                  <CitationList citations={streamingCitations} />
                )}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Error state: the previous implementation only console.error'd
            here, so a real failure (backend down, timeout, Groq error)
            silently reset the input with no visible explanation. */}
        {chatError && (
          <div className="border-t border-destructive/30 bg-destructive/10 px-4 py-3">
            <div className="max-w-4xl mx-auto flex items-center justify-between gap-4">
              <p className="text-sm text-destructive">{chatError}</p>
              <div className="flex items-center gap-2 flex-shrink-0">
                {lastFailedMessage && (
                  <button
                    onClick={() => sendMessage(lastFailedMessage)}
                    className="text-xs font-medium text-destructive hover:underline"
                  >
                    Retry
                  </button>
                )}
                <button
                  onClick={() => setChatError(null)}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Input */}
        <div className="border-t border-border p-4">
          <div className="max-w-4xl mx-auto">
            <div className="flex gap-3 items-end glass rounded-2xl p-3">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a legal question... (Enter to send, Shift+Enter for new line)"
                rows={1}
                className="flex-1 bg-transparent resize-none outline-none text-sm text-foreground placeholder:text-muted-foreground max-h-40 overflow-y-auto"
                style={{ minHeight: '24px' }}
                onInput={(e) => {
                  const el = e.currentTarget
                  el.style.height = 'auto'
                  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
                }}
              />
              <button
                onClick={() => sendMessage()}
                disabled={!input.trim() || isStreaming}
                className="w-8 h-8 rounded-xl bg-primary flex items-center justify-center text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
              >
                {isStreaming ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
            <p className="text-xs text-muted-foreground text-center mt-2">
              Answers grounded in the ChronoLegal corpus. Always verify with official sources.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function PipelineIndicator({ stage }: { stage: PipelineStage }) {
  const order = PIPELINE_STEPS.map((s) => s.key)
  const currentIdx = stage ? order.indexOf(stage) : 0

  return (
    <div className="flex items-center gap-1.5 text-xs">
      {PIPELINE_STEPS.map((step, i) => {
        const state = i < currentIdx ? 'done' : i === currentIdx ? 'active' : 'pending'
        return (
          <div key={step.key} className="flex items-center gap-1.5">
            {state === 'done' && <CheckCircle2 className="w-3.5 h-3.5 text-primary" />}
            {state === 'active' && <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />}
            {state === 'pending' && <div className="w-3.5 h-3.5 rounded-full border border-border" />}
            <span className={state === 'pending' ? 'text-muted-foreground' : 'text-foreground'}>
              {step.label}
            </span>
            {i < PIPELINE_STEPS.length - 1 && (
              <ChevronRight className="w-3 h-3 text-muted-foreground mx-0.5" />
            )}
          </div>
        )
      })}
    </div>
  )
}

function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null)
  const [copied, setCopied] = useState(false)

  async function copyContent() {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  async function submitFeedback(type: 'up' | 'down') {
    setFeedback(type)
    await feedbackApi.submit({
      query: message.content,
      message_id: message.id,
      is_helpful: type === 'up',
    })
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn('flex gap-4', isUser && 'flex-row-reverse')}
    >
      <div className={cn(
        'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
        isUser ? 'bg-primary/20' : 'bg-primary/20',
      )}>
        {isUser ? (
          <User className="w-4 h-4 text-primary" />
        ) : (
          <Bot className="w-4 h-4 text-primary" />
        )}
      </div>

      <div className={cn('flex-1 max-w-3xl', isUser && 'flex flex-col items-end')}>
        {isUser ? (
          <div className="bg-primary/10 border border-primary/20 rounded-2xl rounded-tr-sm px-4 py-3 text-sm">
            {message.content}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="legal-prose">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>

            {message.citations && message.citations.length > 0 && (
              <CitationList citations={message.citations} />
            )}

            <div className="flex items-center gap-2 mt-2">
              <button
                onClick={copyContent}
                className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
              >
                <Copy className="w-3 h-3" />
                {copied ? 'Copied!' : 'Copy'}
              </button>
              <button
                onClick={() => submitFeedback('up')}
                className={cn(
                  'text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors',
                  feedback === 'up' && 'text-primary',
                )}
              >
                <ThumbsUp className="w-3 h-3" />
              </button>
              <button
                onClick={() => submitFeedback('down')}
                className={cn(
                  'text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors',
                  feedback === 'down' && 'text-destructive',
                )}
              >
                <ThumbsDown className="w-3 h-3" />
              </button>
              {message.latency_ms && (
                <span className="text-xs text-muted-foreground ml-auto">
                  {message.latency_ms}ms
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}

function CitationList({ citations }: { citations: Citation[] }) {
  const [expanded, setExpanded] = useState(false)
  const shown = expanded ? citations : citations.slice(0, 3)

  return (
    <div className="mt-3">
      <p className="text-xs font-medium text-muted-foreground mb-2">
        Sources ({citations.length})
      </p>
      <div className="space-y-2">
        {shown.map((c, i) => (
          <motion.div
            key={c.chunk_id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <CitationCard citation={c} index={i} />
          </motion.div>
        ))}
      </div>
      {citations.length > 3 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-primary hover:underline mt-2 flex items-center gap-1"
        >
          {expanded ? 'Show less' : `Show ${citations.length - 3} more`}
          <ChevronRight className={cn('w-3 h-3 transition-transform', expanded && 'rotate-90')} />
        </button>
      )}
    </div>
  )
}
