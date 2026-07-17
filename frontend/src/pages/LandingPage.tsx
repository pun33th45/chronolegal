import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, BookOpen, Brain, Scale, Search, Shield, Zap } from 'lucide-react'

const FEATURES = [
  {
    icon: Brain,
    title: 'AI-Powered Legal QA',
    desc: 'Ask complex legal questions in plain English. Get grounded answers with citations from thousands of real judgments.',
  },
  {
    icon: Search,
    title: 'Semantic Search',
    desc: 'Search by meaning, not just keywords. Our legal embeddings understand context, acts, sections, and legal concepts.',
  },
  {
    icon: Scale,
    title: 'Case Analytics',
    desc: 'Visualize case trends, top courts, most-cited acts, and decision patterns across the Indian legal corpus.',
  },
  {
    icon: Shield,
    title: 'Zero Hallucination',
    desc: 'Every answer is grounded in retrieved documents. If the corpus lacks evidence, the AI tells you — never fabricates.',
  },
  {
    icon: BookOpen,
    title: 'Rich Case Viewer',
    desc: 'Read full judgments with highlighted passages, extracted entities, timeline of events, and related cases.',
  },
  {
    icon: Zap,
    title: 'Streaming Responses',
    desc: 'Real-time streaming responses with live citation discovery. Works like ChatGPT, built for the law.',
  },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background overflow-x-hidden">
      {/* Navbar */}
      <nav className="fixed top-0 inset-x-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-legal-gradient flex items-center justify-center">
              <BookOpen className="w-4 h-4 text-white" />
            </div>
            <span className="font-serif font-bold text-lg gold-text">ChronoLegal</span>
          </div>
          <div className="flex items-center gap-4">
            <Link
              to="/login"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-24 px-6 relative overflow-hidden">
        {/* Background glow */}
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-primary/5 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-40 right-0 w-[400px] h-[400px] bg-legal-teal/5 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-4xl mx-auto text-center relative">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-primary/30 bg-primary/5 text-primary text-xs font-medium mb-6">
              <Zap className="w-3 h-3" />
              Powered by RAG + LLaMA 3.1 + BAAI/bge-large
            </div>
            <h1 className="text-5xl md:text-7xl font-serif font-bold text-foreground leading-tight mb-6">
              Legal Research,{' '}
              <span className="gold-text">Reimagined</span>{' '}
              by AI
            </h1>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
              Search thousands of Indian legal judgments semantically. Ask complex legal questions.
              Get grounded, cited answers — powered by state-of-the-art AI and the ChronoLegal dataset.
            </p>
            <div className="flex items-center justify-center gap-4">
              <Link
                to="/register"
                className="flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground font-semibold rounded-xl hover:bg-primary/90 transition-all hover:scale-105"
              >
                Start Researching
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                to="/login"
                className="px-6 py-3 border border-border text-foreground font-medium rounded-xl hover:bg-accent transition-colors"
              >
                Sign In
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Stats */}
      <section className="py-12 border-y border-border">
        <div className="max-w-5xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[
            ['10,000+', 'Legal Judgments'],
            ['1M+', 'Indexed Passages'],
            ['50+', 'Indian Courts'],
            ['Zero', 'Hallucinations'],
          ].map(([num, label]) => (
            <div key={label}>
              <p className="text-3xl font-bold gold-text">{num}</p>
              <p className="text-sm text-muted-foreground mt-1">{label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-serif font-bold text-foreground mb-4">
              Everything you need for legal research
            </h2>
            <p className="text-muted-foreground">
              Built for lawyers, judges, students, and researchers.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="legal-card"
              >
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <f.icon className="w-5 h-5 text-primary" />
                </div>
                <h3 className="font-semibold text-foreground mb-2">{f.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          className="max-w-3xl mx-auto text-center glass rounded-2xl p-12"
        >
          <h2 className="text-3xl font-serif font-bold text-foreground mb-4">
            Ready to transform your legal research?
          </h2>
          <p className="text-muted-foreground mb-8">
            Join the future of AI-powered legal research. Free to get started.
          </p>
          <Link
            to="/register"
            className="inline-flex items-center gap-2 px-8 py-3 bg-primary text-primary-foreground font-semibold rounded-xl hover:bg-primary/90 transition-all hover:scale-105"
          >
            Create Free Account
            <ArrowRight className="w-4 h-4" />
          </Link>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8 px-6 text-center text-sm text-muted-foreground">
        <p>© 2025 ChronoLegal. AI-powered Legal Research Platform.</p>
        <p className="mt-1 text-xs">Built with LangChain · ChromaDB · BAAI/bge-large · LLaMA 3.1</p>
      </footer>
    </div>
  )
}
