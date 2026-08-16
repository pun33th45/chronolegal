// =============================================================================
// ChronoLegal Type Definitions
// =============================================================================

export interface User {
  id: string
  email: string
  username: string
  full_name: string | null
  avatar_url: string | null
  is_active: boolean
  is_verified: boolean
  is_admin: boolean
  last_login_at: string | null
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface Citation {
  case_id: string
  case_name: string
  citation_text?: string | null
  chunk_id: string
  chunk_text?: string | null
  content: string
  similarity_score: number
  relevance_score?: number
  rank: number
  page_number: number | null
  court: string | null
  date: string | null
  year?: string | null
  acts: string[] | null
  decision_type?: string | null
}

export interface RelatedCase {
  case_id: string
  case_name: string
  court: string | null
  similarity_score: number
  relationship_type: string
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  citations: Citation[] | null
  token_count: number | null
  latency_ms: number | null
  created_at: string
}

export interface Conversation {
  id: string
  user_id: string
  title: string
  is_archived: boolean
  message_count: number
  created_at: string
  updated_at: string
  last_message?: Message | null
  messages?: Message[]
}

export interface ChatRequest {
  conversation_id?: string | null
  message: string
  stream?: boolean
  top_k?: number
  filters?: Record<string, unknown> | null
  include_related_cases?: boolean
}

export interface ChatResponse {
  conversation_id: string
  message_id: string
  answer: string
  citations: Citation[]
  related_cases: RelatedCase[]
  query_rewritten: string | null
  context_used: boolean
  sufficient_context: boolean
  latency_ms: number
  token_count: number | null
  generated_at: string
}

export interface SearchFilters {
  court?: string | null
  judge?: string | null
  date_from?: string | null
  date_to?: string | null
  year_from?: number | null
  year_to?: number | null
  acts?: string[] | null
  act?: string | null
  sections?: string[] | null
  decision_type?: string | null
  min_similarity?: number
  search_type?: string
}

export interface SearchResult {
  case_id: string
  case_name: string
  court: string | null
  judges: string[] | null
  judgment_date: string | null
  decision_date?: string | null
  acts: string[] | null
  chunk_content: string
  chunk_text?: string | null
  summary?: string | null
  decision_type?: string | null
  similarity_score: number
  score?: number
  rank: number
  highlights: string[]
  chunk_id: string | null
  page_number: number | null
}

export interface SearchResponse {
  query: string
  rewritten_query: string | null
  results: SearchResult[]
  total_results: number
  search_type: string
  latency_ms: number
}

export interface LegalCase {
  id: string
  case_id: string
  case_name: string
  case_number: string | null
  petitioner: string | null
  respondent: string | null
  parties: string[] | null
  court: string | null
  bench: string | null
  judges: string[] | null
  judgment_date: string | null
  acts: string[] | null
  sections: string[] | null
  keywords: string[] | null
  full_text: string | null
  summary: string | null
  headnotes: string | null
  decision_type: string | null
  outcome: string | null
  text_length: number | null
  cited_cases: string[] | null
  citation_count: number
  chunk_count: number
  is_embedded: boolean
  created_at: string
}

export interface LegalCaseSummary {
  id: string
  case_id: string
  case_name: string
  court: string | null
  judges: string[] | null
  judgment_date: string | null
  acts: string[] | null
  decision_type: string | null
  summary: string | null
  citation_count: number
}

export interface SimilarCaseResult {
  case_id: string
  case_name: string
  court: string | null
  similarity_score: number
}

export interface LegalEntities {
  judges: string[]
  courts: string[]
  acts: string[]
  sections: string[]
  lawyers: string[]
  organizations: string[]
  dates: string[]
  locations: string[]
  parties: string[]
}

export interface TimelineEvent {
  date: string
  event: string
  description: string | null
}

export interface SummaryResponse {
  case_id: string
  case_name: string
  summary_type: string
  summary: string
  generated_at: string
}

export interface AnalyticsDashboard {
  total_cases: number
  total_embeddings: number
  total_users: number
  total_searches: number
  top_acts: { name: string; count: number }[]
  top_courts: { court: string; count: number; percentage: number }[]
  top_judges: { name: string; count: number }[]
  top_keywords: { name: string; count: number }[]
  case_trends: { year: number; count: number }[]
  decision_types: { decision_type: string; count: number; percentage: number }[]
  avg_text_length: number
  avg_search_latency_ms: number
  storage_used_mb: number
}

export interface AdminStats {
  total_cases: number
  embedded_cases: number
  pending_embedding: number
  total_chunks: number
  chroma_collection_count: number
  total_users: number
  active_users_today: number
  total_searches_today: number
  avg_latency_ms: number
  cache_hit_rate: number
  storage_used_mb: number
}

export type SummaryType = 'concise' | 'detailed' | 'bullet'
export type SearchType = 'semantic' | 'hybrid' | 'keyword'

export interface StreamChunk {
  type: 'text' | 'citation' | 'done' | 'error'
  content?: string | null
  citations?: Citation[] | null
  conversation_id?: string | null
  message_id?: string | null
  error?: string | null
}

export interface ApiError {
  detail: string
  type?: string
}
