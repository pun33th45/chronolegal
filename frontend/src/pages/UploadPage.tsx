import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { ArrowRight, CheckCircle2, FileText, FileUp, Loader2, X, XCircle } from 'lucide-react'
import { casesApi, documentsApi, type UploadStatus } from '@/services/api'
import { Button } from '@/components/ui/Button'

const STAGES: { key: UploadStatus['status']; emoji: string; label: string }[] = [
  { key: 'extracting', emoji: '📄', label: 'Extracting judgment' },
  { key: 'chunking', emoji: '✂️', label: 'Legal structure-aware chunking' },
  { key: 'extracting_entities', emoji: '⚖️', label: 'Extracting legal entities' },
  { key: 'embedding', emoji: '🧠', label: 'Generating LegalBERT embeddings' },
  { key: 'indexing', emoji: '🔎', label: 'Indexing into the legal knowledge base' },
  { key: 'done', emoji: '✅', label: 'Ready for research' },
]

const PIPELINE_STEPS = ['Judgment', 'LegalBERT', 'Vector Search', 'Reranking', 'Groq', 'Cited Answer']

function stageState(stageKey: UploadStatus['status'], currentStatus: UploadStatus['status']) {
  const order = STAGES.map((s) => s.key)
  const stageIdx = order.indexOf(stageKey)
  const currentIdx = order.indexOf(currentStatus)
  if (currentStatus === 'failed') return stageIdx < currentIdx ? 'done' : 'pending'
  if (stageIdx < currentIdx) return 'done'
  if (stageIdx === currentIdx) return 'active'
  return 'pending'
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [status, setStatus] = useState<UploadStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const isDone = status?.status === 'done'
  const { data: newCase } = useQuery({
    queryKey: ['case', status?.case_id],
    queryFn: () => casesApi.get(status!.case_id!),
    enabled: isDone && !!status?.case_id,
  })

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setError(null)
    setStatus(null)
    try {
      const { task_id } = await documentsApi.upload(file)
      pollRef.current = setInterval(async () => {
        try {
          const s = await documentsApi.status(task_id)
          setStatus(s)
          if (s.status === 'done' || s.status === 'failed') {
            stopPolling()
            setUploading(false)
          }
        } catch {
          stopPolling()
          setUploading(false)
          setError('Lost connection while checking processing status.')
        }
      }, 2000)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Upload failed')
      setUploading(false)
    }
  }

  function reset() {
    stopPolling()
    setFile(null)
    setStatus(null)
    setError(null)
    setUploading(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-bold text-foreground mb-1">Add a Judgment to the Knowledge Base</h2>
        <p className="text-sm text-muted-foreground">
          Upload a legal judgment to extract its structure, identify legal entities, generate
          LegalBERT embeddings, and make it available for research.
        </p>
      </div>

      {!status && (
        <div className="legal-card space-y-4">
          {!file ? (
            <label className="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-border rounded-xl py-12 cursor-pointer hover:border-primary/50 hover:bg-accent/50 transition-colors">
              <FileUp className="w-8 h-8 text-muted-foreground" />
              <span className="text-sm text-foreground">Click to browse</span>
              <span className="text-xs text-muted-foreground">PDF, DOC, DOCX, or TXT</span>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
          ) : (
            <div className="flex items-center gap-3 border border-border rounded-xl p-4">
              <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                <FileText className="w-4 h-4 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{file.name}</p>
                <p className="text-xs text-muted-foreground">{formatBytes(file.size)}</p>
              </div>
              <button
                onClick={() => {
                  setFile(null)
                  if (fileInputRef.current) fileInputRef.current.value = ''
                }}
                aria-label="Remove file"
                className="w-7 h-7 rounded-lg flex items-center justify-center text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors flex-shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {error && (
            <p className="text-sm text-destructive flex items-center gap-2">
              <XCircle className="w-4 h-4" /> {error}
            </p>
          )}

          <Button onClick={handleUpload} disabled={!file || uploading} loading={uploading} className="w-full">
            Process Judgment
          </Button>
        </div>
      )}

      {status && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="legal-card space-y-4"
        >
          <p className="text-sm font-medium text-foreground">{status.filename}</p>

          <div className="space-y-3">
            {STAGES.map((stage) => {
              const state = stageState(stage.key, status.status)
              return (
                <div key={stage.key} className="flex items-center gap-3 text-sm">
                  {state === 'done' && <CheckCircle2 className="w-4 h-4 text-primary flex-shrink-0" />}
                  {state === 'active' && (
                    <Loader2 className="w-4 h-4 text-primary animate-spin flex-shrink-0" />
                  )}
                  {state === 'pending' && (
                    <div className="w-4 h-4 rounded-full border border-border flex-shrink-0" />
                  )}
                  <span aria-hidden="true">{stage.emoji}</span>
                  <span
                    className={
                      state === 'pending' ? 'text-muted-foreground' : 'text-foreground'
                    }
                  >
                    {stage.label}
                  </span>
                </div>
              )
            })}
          </div>

          {status.status === 'failed' && (
            <p className="text-sm text-destructive flex items-center gap-2">
              <XCircle className="w-4 h-4" /> {status.error || 'Unable to process this judgment.'}
            </p>
          )}

          {isDone && (
            <div className="pt-2 space-y-4 border-t border-border">
              <p className="text-sm font-medium text-primary pt-4">Judgment successfully added</p>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs text-muted-foreground">Case Name</p>
                  <p className="text-foreground">{newCase?.case_name ?? '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Court</p>
                  <p className="text-foreground">{newCase?.court ?? '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Date</p>
                  <p className="text-foreground">{newCase?.judgment_date ?? '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Judges</p>
                  <p className="text-foreground">
                    {newCase?.judges && newCase.judges.length > 0 ? newCase.judges.join(', ') : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Chunks Indexed</p>
                  <p className="text-foreground">{status.chunk_count ?? status.chunks}</p>
                </div>
              </div>

              {status.case_id && (
                <div className="flex flex-wrap gap-3">
                  <Link to={`/chat?case=${status.case_id}&name=${encodeURIComponent(newCase?.case_name ?? status.filename)}`}>
                    <Button className="gap-2">
                      Research this Judgment
                      <ArrowRight className="w-4 h-4" />
                    </Button>
                  </Link>
                  <Link to={`/cases/${status.case_id}`}>
                    <Button variant="secondary">View Case</Button>
                  </Link>
                </div>
              )}
            </div>
          )}

          {(status.status === 'done' || status.status === 'failed') && (
            <button
              onClick={reset}
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Upload another document
            </button>
          )}
        </motion.div>
      )}

      <div className="legal-card">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
          How ChronoLegal works
        </p>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {PIPELINE_STEPS.map((step, i) => (
            <div key={step} className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded-lg bg-accent text-foreground">{step}</span>
              {i < PIPELINE_STEPS.length - 1 && (
                <ArrowRight className="w-3.5 h-3.5 text-muted-foreground" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
