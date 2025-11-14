"""
Local LLM integration with RAG for report generation and Q&A
"""
from .rag_system import RAGSystem
from .report_generator import ReportGenerator
from .chat_interface import (
    ChatInterface,
    check_ollama_installation,
    get_available_models,
    download_recommended_model
)

__all__ = [
    'RAGSystem',
    'ReportGenerator',
    'ChatInterface',
    'check_ollama_installation',
    'get_available_models',
    'download_recommended_model'
]
