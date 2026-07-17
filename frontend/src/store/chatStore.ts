import { create } from 'zustand'
import type { Citation, Conversation, Message } from '@/types'

interface ChatState {
  conversations: Conversation[]
  activeConversationId: string | null
  messages: Message[]
  isStreaming: boolean
  streamingContent: string
  pendingCitations: Citation[]

  setConversations: (convs: Conversation[]) => void
  setActiveConversation: (id: string | null) => void
  setMessages: (messages: Message[]) => void
  addMessage: (message: Message) => void
  updateLastMessage: (content: string) => void
  setStreaming: (v: boolean) => void
  appendStreamChunk: (chunk: string) => void
  setPendingCitations: (citations: Citation[]) => void
  clearStreamingState: () => void
  addConversation: (conv: Conversation) => void
  updateConversation: (id: string, updates: Partial<Conversation>) => void
  removeConversation: (id: string) => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  messages: [],
  isStreaming: false,
  streamingContent: '',
  pendingCitations: [],

  setConversations: (convs) => set({ conversations: convs }),
  setActiveConversation: (id) => set({ activeConversationId: id }),
  setMessages: (messages) => set({ messages }),

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  updateLastMessage: (content) =>
    set((state) => {
      const messages = [...state.messages]
      const last = messages[messages.length - 1]
      if (last) {
        messages[messages.length - 1] = { ...last, content }
      }
      return { messages }
    }),

  setStreaming: (v) => set({ isStreaming: v }),

  appendStreamChunk: (chunk) =>
    set((state) => ({ streamingContent: state.streamingContent + chunk })),

  setPendingCitations: (citations) => set({ pendingCitations: citations }),

  clearStreamingState: () =>
    set({ isStreaming: false, streamingContent: '', pendingCitations: [] }),

  addConversation: (conv) =>
    set((state) => ({ conversations: [conv, ...state.conversations] })),

  updateConversation: (id, updates) =>
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, ...updates } : c,
      ),
    })),

  removeConversation: (id) =>
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      activeConversationId:
        state.activeConversationId === id ? null : state.activeConversationId,
    })),
}))
