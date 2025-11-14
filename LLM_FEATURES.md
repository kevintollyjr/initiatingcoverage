# Local LLM Features

## Overview

The equity research application now includes powerful AI features powered by local open-source LLMs through Ollama. These features enable:

1. **Automated Report Generation**: Generate comprehensive initiating coverage reports
2. **Interactive Chat Q&A**: Ask questions about collected documents with context-aware responses

## Prerequisites

### 1. Install Ollama

Ollama is a local LLM runtime that runs models on your machine.

**Installation:**
- **macOS/Linux**: `curl https://ollama.ai/install.sh | sh`
- **Windows**: Download from [https://ollama.ai](https://ollama.ai)
- **Manual**: Visit [https://ollama.ai](https://ollama.ai) for detailed instructions

**Verify Installation:**
```bash
ollama --version
```

### 2. Download an LLM Model

Recommended models for equity research:

**Llama 3.1 8B** (Recommended - balanced speed/quality)
```bash
ollama pull llama3.1:8b
```

**Llama 3.1 70B** (Best quality, requires 40GB+ RAM)
```bash
ollama pull llama3.1:70b
```

**Mistral** (Fast, good for simple queries)
```bash
ollama pull mistral
```

**Phi-3** (Lightweight, good for low-resource machines)
```bash
ollama pull phi3
```

### 3. Install Python Dependencies

```bash
pip install ollama chromadb sentence-transformers langchain
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

## Features

### 🤖 AI Report Generation

**Location:** "AI Report" tab in the main app

**What it does:**
- Indexes all collected documents (SEC filings, IR presentations, management profiles, segments, market data)
- Uses RAG (Retrieval Augmented Generation) to extract relevant context
- Generates a comprehensive initiating coverage report with:
  - Executive Summary
  - Company Overview
  - Business Segments Analysis
  - Management Team Assessment
  - Financial Analysis
  - Investment Thesis
  - Key Risks

**How to use:**
1. Collect data for a ticker (run the pipeline first)
2. Navigate to the "🤖 AI Report" tab
3. Select your preferred LLM model
4. Click "📝 Generate Report"
5. Wait for generation (3-10 minutes depending on model and hardware)
6. Review and download the generated report

**Output:**
- Markdown report displayed in the app
- Saved to: `data/{TICKER}/{TICKER}_initiating_coverage_report.md`
- Downloadable via the "📥 Download Report" button

### 💬 Chat Q&A

**Location:** "Chat Q&A" tab in the main app

**What it does:**
- Interactive chat interface for asking questions about the company
- Uses RAG to retrieve relevant context from all documents
- Provides source citations for answers
- Maintains conversation history for context

**How to use:**
1. Ensure data is collected for the ticker
2. Navigate to the "💬 Chat Q&A" tab
3. Select your preferred LLM model
4. Ask questions in the chat input
5. Review answers with source citations

**Example questions:**
- "What are the company's main revenue drivers?"
- "Who is the CEO and what is their background?"
- "What risks does the company face?"
- "How has revenue grown over the past 5 years?"
- "What are the company's competitive advantages?"
- "What do the recent 10-K filings say about business strategy?"

**Features:**
- **Source Citations**: Each answer includes references to source documents
- **Conversation History**: Context is maintained across questions
- **Export**: Save conversations to markdown files
- **Clear History**: Reset conversation to start fresh

## How RAG Works

**RAG (Retrieval Augmented Generation)** combines document retrieval with LLM generation:

1. **Indexing Phase:**
   - All documents are split into chunks (1000 characters)
   - Each chunk is converted to a vector embedding
   - Embeddings are stored in ChromaDB (local vector database)

2. **Query Phase:**
   - User question is converted to a vector embedding
   - Most relevant document chunks are retrieved via similarity search
   - Retrieved context + question are sent to the LLM
   - LLM generates answer based on the provided context

**Advantages:**
- Answers are grounded in actual documents
- No hallucination of facts not in the data
- Sources can be verified
- Works with local models (no API costs)
- Private - data never leaves your machine

## Technical Architecture

### Components

1. **RAG System** (`src/llm/rag_system.py`)
   - Document indexing
   - Vector storage (ChromaDB)
   - Similarity search
   - Context retrieval

2. **Report Generator** (`src/llm/report_generator.py`)
   - Report structure and templates
   - Section-by-section generation
   - Context gathering for each section
   - Report compilation

3. **Chat Interface** (`src/llm/chat_interface.py`)
   - Conversation management
   - Context-aware prompting
   - History tracking
   - Export functionality

### Data Flow

```
Documents → Text Extraction → Chunking → Embeddings → Vector DB
                                                          ↓
User Query → Embedding → Similarity Search → Context → LLM → Answer
```

### Models Used

**Embeddings:** `all-MiniLM-L6-v2` (sentence-transformers)
- Lightweight local model
- 384-dimensional vectors
- Fast encoding (~1000 sentences/second)
- No API key required

**LLM:** User-selected Ollama model
- Runs locally on your machine
- Supports GPU acceleration (if available)
- No API costs
- Full privacy

## Performance Considerations

### Model Selection

| Model | Size | RAM Required | Speed | Quality | Best For |
|-------|------|--------------|-------|---------|----------|
| phi3 | 2.3GB | 4GB | Fast | Good | Quick queries, low-resource |
| mistral | 4GB | 8GB | Fast | Very Good | General use |
| llama3.1:8b | 4.7GB | 8GB | Medium | Excellent | **Recommended** |
| llama3.1:70b | 40GB | 48GB+ | Slow | Best | High-quality analysis |

### Indexing Performance

- **Small dataset** (< 100 MB): 1-2 minutes
- **Medium dataset** (100-500 MB): 3-5 minutes
- **Large dataset** (500MB+): 5-15 minutes

**Note:** Indexing only happens once per ticker. Subsequent queries use cached embeddings.

### Generation Time

Report generation time varies by model:
- **phi3**: 2-5 minutes
- **mistral**: 3-7 minutes
- **llama3.1:8b**: 5-10 minutes
- **llama3.1:70b**: 15-30 minutes

## Troubleshooting

### "Ollama not available"

**Problem:** Ollama package not installed or server not running

**Solutions:**
1. Install Ollama from https://ollama.ai
2. Start Ollama server: `ollama serve`
3. Install Python package: `pip install ollama`

### "No models available"

**Problem:** No LLM models downloaded

**Solution:**
```bash
ollama pull llama3.1:8b
```

### "RAG dependencies not available"

**Problem:** Required packages not installed

**Solution:**
```bash
pip install chromadb sentence-transformers langchain
```

### Slow performance

**Solutions:**
1. Use a smaller model (phi3 or mistral)
2. Reduce `n_context_chunks` in queries
3. Enable GPU acceleration (if available)
4. Close other applications to free RAM

### Out of memory errors

**Solutions:**
1. Use a smaller model
2. Close other applications
3. Increase swap space (Linux/Mac)
4. Consider cloud deployment for larger models

## Privacy & Security

**All processing is local:**
- Documents never leave your machine
- No API calls to external services (except initial model download)
- Vector database stored locally
- Complete data privacy

**Data storage locations:**
- Vector DB: `data/{TICKER}/vector_db/`
- Generated reports: `data/{TICKER}/{TICKER}_initiating_coverage_report.md`
- Chat exports: `data/{TICKER}/{TICKER}_chat_conversation.md`

## Best Practices

### For Report Generation

1. **Collect comprehensive data first**: Run the full pipeline with all settings enabled
2. **Use appropriate model**: llama3.1:8b for balanced performance
3. **Review and edit**: AI-generated reports should be reviewed by humans
4. **Update regularly**: Re-generate reports after collecting new data

### For Chat Q&A

1. **Be specific**: Ask clear, focused questions
2. **Check sources**: Review cited documents for verification
3. **Follow up**: Use conversation history to ask clarifying questions
4. **Export important conversations**: Save valuable Q&A sessions

### Model Selection

- **Quick exploration**: phi3 or mistral
- **Production reports**: llama3.1:8b or llama3.1:70b
- **Resource-constrained**: phi3
- **Highest quality**: llama3.1:70b (if you have the RAM)

## Example Workflow

1. **Collect Data**
   ```
   - Enter ticker: MSFT
   - Enable all data sources
   - Run pipeline
   ```

2. **Generate Report**
   ```
   - Go to "AI Report" tab
   - Select model: llama3.1:8b
   - Click "Generate Report"
   - Wait 5-10 minutes
   - Review and download
   ```

3. **Ask Questions**
   ```
   - Go to "Chat Q&A" tab
   - Ask: "What are Microsoft's main business segments?"
   - Review answer and sources
   - Follow up: "Which segment is growing fastest?"
   - Export conversation
   ```

## Limitations

1. **Quality depends on source data**: Answers are only as good as the collected documents
2. **Not financial advice**: AI-generated content should not be used as sole basis for investment decisions
3. **May miss nuance**: Complex financial concepts may be oversimplified
4. **Requires manual review**: All generated content should be reviewed by qualified analysts
5. **Hardware requirements**: Larger models require significant RAM
6. **Generation time**: High-quality reports take time to generate

## Future Enhancements

Potential improvements for future releases:

1. **Fine-tuned models**: Models specifically trained on financial analysis
2. **Multi-document comparison**: Compare multiple companies
3. **Automated updates**: Re-generate reports when new filings arrive
4. **Custom prompts**: User-defined report templates
5. **Quantitative analysis**: Integration with financial models
6. **Voice interface**: Ask questions via voice
7. **Collaborative editing**: Team annotations on generated reports

## Support & Resources

- **Ollama Documentation**: https://ollama.ai/docs
- **Model Library**: https://ollama.ai/library
- **ChromaDB Docs**: https://docs.trychroma.com
- **Sentence Transformers**: https://www.sbert.net
- **LangChain**: https://python.langchain.com

## Feedback

Have suggestions for improving the AI features? Please open an issue on the GitHub repository.

---

**Last Updated**: 2025-11-14
