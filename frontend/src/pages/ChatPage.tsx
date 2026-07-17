import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Bot,
  ChevronRight,
  Copy,
  Loader2,
  Plus,
  Send,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  User,
} from 'lucide-react'
import { chatApi, feedbackApi } from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/utils/cn'
import type { Citation, Conversation, Message } from '@/types'

const SUGGESTED = [
  'Explain Article 21 of the Indian Constitution.',
  'What is the doctrine of basic structure?',
  'Landmark cases on free speech in India.',
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
  const [activeConvId, setActiveConvId] = useState<string | null>(conversationId || null)

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

  const messages = activeConv?.messages || []

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
  }, [searchParams])

  async function sendMessage() {
    if (!input.trim() || isStreaming) return
    const userMessage = input.trim()
    setInput('')
    setIsStreaming(true)
    setStreamingText('')
    setStreamingCitations([])

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
        }),
      })

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
            if (chunk.type === 'text') {
              setStreamingText((prev) => prev + (chunk.content || ''))
            } else if (chunk.type === 'citation') {
              setStreamingCitations(chunk.citations || [])
            } else if (chunk.type === 'done') {
              if (chunk.conversation_id) convId = chunk.conversation_id
            }
          } catch {}
        }
      }

      if (convId && convId !== activeConvId) {
        setActiveConvId(convId)
        navigate(`/chat/${convId}`, { replace: true })
      }

      await qc.invalidateQueries({ queryKey: ['conversations'] })
      await refetchConv()
    } catch (err) {
      console.error('Stream error:', err)
    } finally {
      setIsStreaming(false)
      setStreamingText('')
      setStreamingCitations([])
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
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {!activeConvId && messages.length === 0 && !isStreaming && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                <Bot className="w-8 h-8 text-primary" />
              </div>
              <h2 className="text-xl font-semibold text-foreground mb-2">ChronoLegal AI</h2>
              <p className="text-muted-foreground mb-8 max-w-sm">
                Ask any legal question. I'll search thousands of Indian judgments and give you grounded, cited answers.
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
                  <div className="flex items-center gap-2 text-muted-foreground text-sm">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Searching legal corpus...
                  </div>
                )}
                {streamingCitations.length > 0 && (
                  <CitationList citations={streamingCitations} />
                )}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

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
                onClick={sendMessage}
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
            className="citation-badge w-full text-left block"
          >
            <span className="font-semibold mr-1">[{c.rank}]</span>
            {c.case_name}
            {c.court && <span className="text-primary/60 ml-1">· {c.court}</span>}
            <span className="ml-1 text-primary/50">
              ({(c.similarity_score * 100).toFixed(0)}% match)
            </span>
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
