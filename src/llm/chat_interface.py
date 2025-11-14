"""
Chat Interface for Q&A on collected documents
Uses RAG + LLM for context-aware responses
"""
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

from .rag_system import RAGSystem

logger = logging.getLogger(__name__)

# Optional Ollama support
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("ollama not available - chat will be disabled")


class ChatInterface:
    """Interactive chat interface for document Q&A"""

    def __init__(
        self,
        data_dir: Path,
        ticker: str,
        model_name: str = "llama3.1:8b"
    ):
        """
        Initialize chat interface

        Args:
            data_dir: Path to data directory
            ticker: Stock ticker
            model_name: Ollama model name
        """
        self.data_dir = data_dir
        self.ticker = ticker
        self.model_name = model_name

        # Chat history
        self.history: List[Dict[str, str]] = []

        # Check if Ollama is available
        if not OLLAMA_AVAILABLE:
            logger.error("Ollama not available")
            self.available = False
            return

        # Check if model is available
        try:
            models = ollama.list()
            model_names = [m['name'] for m in models.get('models', [])]
            if not any(model_name in name for name in model_names):
                logger.warning(f"Model {model_name} not found in Ollama")
                self.available = False
                return
        except Exception as e:
            logger.error(f"Error checking Ollama models: {e}")
            self.available = False
            return

        self.available = True

        # Initialize RAG system
        self.rag = RAGSystem(data_dir, ticker)
        if not self.rag.available:
            logger.error("RAG system not available")
            self.available = False

        logger.info(f"Chat interface initialized for {ticker}")

    def ask(
        self,
        question: str,
        n_context_chunks: int = 5,
        include_sources: bool = True
    ) -> Tuple[str, Optional[List[Dict]]]:
        """
        Ask a question about the documents

        Args:
            question: User's question
            n_context_chunks: Number of context chunks to retrieve
            include_sources: Whether to return source citations

        Returns:
            Tuple of (answer, sources)
        """
        if not self.available:
            return "Chat system not available. Please install ollama and required dependencies.", None

        # Retrieve relevant context
        context_results = self.rag.query(question, n_results=n_context_chunks)

        if not context_results:
            return "I couldn't find relevant information in the documents to answer that question.", None

        # Build context string
        context = self._format_context(context_results)

        # Build prompt with chat history
        prompt = self._build_prompt(question, context)

        # Get response from LLM
        answer = self._call_llm(prompt)

        # Add to history
        self.history.append({
            'question': question,
            'answer': answer,
            'context_sources': len(context_results)
        })

        # Return answer and sources
        sources = context_results if include_sources else None
        return answer, sources

    def _format_context(self, results: List[Dict]) -> str:
        """Format context results for the prompt"""
        context = ""
        for i, result in enumerate(results, 1):
            source_type = result['metadata'].get('source', 'unknown')
            context += f"\n[Context {i} - {source_type}]:\n"
            context += result['text'] + "\n"

        return context

    def _build_prompt(self, question: str, context: str) -> str:
        """Build the complete prompt including context and history"""

        # Base system message
        system_msg = f"""You are an AI analyst helping answer questions about {self.ticker}.

You have access to various documents including SEC filings, investor presentations,
management profiles, business segment information, and market data.

IMPORTANT INSTRUCTIONS:
1. Answer based ONLY on the provided context
2. If the context doesn't contain enough information, say so
3. Be precise and cite specific facts when possible
4. If asked about numbers/metrics, only provide what's in the context
5. Do not make up or infer information not present in the context

"""

        # Add recent history for continuity
        history_context = ""
        if len(self.history) > 0:
            history_context = "\n\nRecent Conversation:\n"
            for item in self.history[-3:]:  # Last 3 exchanges
                history_context += f"Q: {item['question']}\n"
                history_context += f"A: {item['answer']}\n\n"

        # Build full prompt
        full_prompt = f"""{system_msg}

{history_context}

Context from documents:
{context}

Current Question: {question}

Please provide a clear, factual answer based on the context above:"""

        return full_prompt

    def _call_llm(self, prompt: str, max_tokens: int = 500) -> str:
        """
        Call the LLM with a prompt

        Args:
            prompt: The prompt to send
            max_tokens: Maximum response length

        Returns:
            Generated answer
        """
        try:
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    'num_predict': max_tokens,
                    'temperature': 0.3,  # Lower temperature for factual Q&A
                }
            )
            return response['response']

        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return f"Error generating response: {str(e)}"

    def clear_history(self):
        """Clear chat history"""
        self.history = []
        logger.info("Chat history cleared")

    def get_history(self) -> List[Dict[str, str]]:
        """Get chat history"""
        return self.history

    def export_conversation(self, output_path: Path):
        """
        Export conversation to markdown file

        Args:
            output_path: Where to save the conversation
        """
        content = f"# Chat Conversation: {self.ticker}\n\n"
        content += f"**Total Questions:** {len(self.history)}\n\n---\n\n"

        for i, item in enumerate(self.history, 1):
            content += f"## Question {i}\n\n"
            content += f"**Q:** {item['question']}\n\n"
            content += f"**A:** {item['answer']}\n\n"
            content += f"*Sources: {item['context_sources']} document chunks*\n\n"
            content += "---\n\n"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Conversation exported to {output_path}")


def check_ollama_installation() -> Tuple[bool, str]:
    """
    Check if Ollama is installed and running

    Returns:
        Tuple of (is_available, status_message)
    """
    if not OLLAMA_AVAILABLE:
        return False, "Ollama package not installed. Install with: pip install ollama"

    try:
        models = ollama.list()
        model_count = len(models.get('models', []))
        return True, f"Ollama is running with {model_count} models available"
    except Exception as e:
        return False, f"Ollama not running or not accessible: {str(e)}"


def get_available_models() -> List[str]:
    """
    Get list of available Ollama models

    Returns:
        List of model names
    """
    if not OLLAMA_AVAILABLE:
        return []

    try:
        models = ollama.list()
        return [m['name'] for m in models.get('models', [])]
    except Exception:
        return []


def download_recommended_model(model_name: str = "llama3.1:8b") -> bool:
    """
    Download a recommended model for the chat interface

    Args:
        model_name: Model to download (default: llama3.1:8b)

    Returns:
        True if successful, False otherwise
    """
    if not OLLAMA_AVAILABLE:
        logger.error("Ollama not available")
        return False

    try:
        logger.info(f"Downloading {model_name}... This may take several minutes.")
        ollama.pull(model_name)
        logger.info(f"Successfully downloaded {model_name}")
        return True
    except Exception as e:
        logger.error(f"Error downloading model: {e}")
        return False
