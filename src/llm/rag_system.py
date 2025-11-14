"""
RAG (Retrieval Augmented Generation) System
Indexes all collected documents and provides context-aware retrieval
"""
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging
import json

logger = logging.getLogger(__name__)

# Optional imports with graceful fallback
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("chromadb not available - RAG system will be disabled")

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence-transformers not available - embeddings disabled")

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    # Fallback text splitter
    logger.warning("langchain not available - using simple text splitter")


class SimpleTextSplitter:
    """Simple text splitter for when LangChain is not available"""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start = end - self.chunk_overlap
        return chunks


class RAGSystem:
    """Document indexing and retrieval system"""

    def __init__(self, data_dir: Path, ticker: str):
        self.data_dir = data_dir
        self.ticker = ticker
        self.db_dir = data_dir / "vector_db"
        self.db_dir.mkdir(exist_ok=True)

        # Check availability
        if not CHROMADB_AVAILABLE or not EMBEDDINGS_AVAILABLE:
            logger.error("RAG dependencies not available")
            self.available = False
            return

        self.available = True

        # Initialize embeddings model (local, no API needed)
        logger.info("Loading embeddings model...")
        self.embeddings_model = SentenceTransformer('all-MiniLM-L6-v2')

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=str(self.db_dir),
            settings=Settings(anonymized_telemetry=False)
        )

        # Create or get collection
        self.collection_name = f"{ticker}_documents"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"ticker": ticker}
        )

        # Text splitter
        if LANGCHAIN_AVAILABLE:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len
            )
        else:
            self.text_splitter = SimpleTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )

        logger.info(f"RAG system initialized for {ticker}")

    def index_all_documents(
        self,
        progress_callback: Optional[callable] = None
    ) -> int:
        """
        Index all documents in the data directory

        Returns:
            Number of chunks indexed
        """
        if not self.available:
            logger.error("RAG system not available")
            return 0

        if progress_callback:
            progress_callback("Indexing documents for RAG...")

        total_chunks = 0

        # Index SEC filings
        sec_dir = self.data_dir / "sec_filings"
        if sec_dir.exists():
            chunks = self._index_sec_filings(sec_dir)
            total_chunks += chunks
            if progress_callback:
                progress_callback(f"Indexed {chunks} chunks from SEC filings")

        # Index IR presentations metadata
        ir_dir = self.data_dir / "ir"
        if ir_dir.exists():
            chunks = self._index_ir_presentations(ir_dir)
            total_chunks += chunks
            if progress_callback:
                progress_callback(f"Indexed {chunks} chunks from IR presentations")

        # Index website content
        website_dir = self.data_dir / "website"
        if website_dir.exists():
            chunks = self._index_website_content(website_dir)
            total_chunks += chunks
            if progress_callback:
                progress_callback(f"Indexed {chunks} chunks from website")

        # Index market data
        market_file = self.data_dir / "market" / "basic_fundamentals.json"
        if market_file.exists():
            chunks = self._index_market_data(market_file)
            total_chunks += chunks

        if progress_callback:
            progress_callback(f"Total indexed: {total_chunks} document chunks")

        return total_chunks

    def _index_sec_filings(self, sec_dir: Path) -> int:
        """Index SEC filings text"""
        chunks_count = 0

        for form_dir in sec_dir.iterdir():
            if not form_dir.is_dir():
                continue

            form_type = form_dir.name

            # Index text extracts
            for txt_file in form_dir.glob("*.txt"):
                try:
                    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()

                    # Split into chunks
                    if LANGCHAIN_AVAILABLE:
                        chunks = self.text_splitter.split_text(text)
                    else:
                        chunks = self.text_splitter.split_text(text)

                    # Add to collection
                    for i, chunk in enumerate(chunks):
                        chunk_id = f"{form_type}_{txt_file.stem}_chunk_{i}"
                        embedding = self.embeddings_model.encode(chunk).tolist()

                        self.collection.add(
                            ids=[chunk_id],
                            embeddings=[embedding],
                            documents=[chunk],
                            metadatas=[{
                                "source": "sec_filing",
                                "form_type": form_type,
                                "file": txt_file.name,
                                "chunk_index": i
                            }]
                        )
                        chunks_count += 1

                except Exception as e:
                    logger.error(f"Error indexing {txt_file}: {e}")

        return chunks_count

    def _index_ir_presentations(self, ir_dir: Path) -> int:
        """Index IR presentations metadata"""
        chunks_count = 0

        # Index presentations metadata
        pres_index = ir_dir / "presentations" / "presentations_index.json"
        if pres_index.exists():
            try:
                with open(pres_index, 'r') as f:
                    presentations = json.load(f)

                for pres in presentations:
                    # Create summary text
                    text = f"Presentation: {pres.get('title', 'Unknown')}\n"
                    text += f"Date: {pres.get('date', 'Unknown')}\n"
                    text += f"Type: {pres.get('pres_type', 'presentation')}\n"

                    chunk_id = f"ir_pres_{pres.get('date', 'unknown')}_{len(chunks_count)}"
                    embedding = self.embeddings_model.encode(text).tolist()

                    self.collection.add(
                        ids=[chunk_id],
                        embeddings=[embedding],
                        documents=[text],
                        metadatas=[{
                            "source": "ir_presentation",
                            "title": pres.get('title', ''),
                            "date": pres.get('date', '')
                        }]
                    )
                    chunks_count += 1

            except Exception as e:
                logger.error(f"Error indexing IR presentations: {e}")

        return chunks_count

    def _index_website_content(self, website_dir: Path) -> int:
        """Index website content"""
        chunks_count = 0

        # Index management profiles
        mgmt_file = website_dir / "management_team.json"
        if mgmt_file.exists():
            try:
                with open(mgmt_file, 'r') as f:
                    profiles = json.load(f)

                for profile in profiles:
                    text = f"Name: {profile.get('name', '')}\n"
                    text += f"Title: {profile.get('title', '')}\n"
                    text += f"Category: {profile.get('category', '')}\n"
                    text += f"Bio: {profile.get('bio', '')}\n"

                    chunk_id = f"mgmt_{profile.get('name', 'unknown').replace(' ', '_')}"
                    embedding = self.embeddings_model.encode(text).tolist()

                    self.collection.add(
                        ids=[chunk_id],
                        embeddings=[embedding],
                        documents=[text],
                        metadatas=[{
                            "source": "management",
                            "name": profile.get('name', ''),
                            "title": profile.get('title', '')
                        }]
                    )
                    chunks_count += 1

            except Exception as e:
                logger.error(f"Error indexing management: {e}")

        # Index business segments
        seg_file = website_dir / "segments.json"
        if seg_file.exists():
            try:
                with open(seg_file, 'r') as f:
                    segments = json.load(f)

                for segment in segments:
                    text = f"Segment: {segment.get('name', '')}\n"
                    text += f"Description: {segment.get('description', '')}\n"
                    text += f"Category: {segment.get('category', '')}\n"

                    chunk_id = f"segment_{segment.get('name', 'unknown').replace(' ', '_')}"
                    embedding = self.embeddings_model.encode(text).tolist()

                    self.collection.add(
                        ids=[chunk_id],
                        embeddings=[embedding],
                        documents=[text],
                        metadatas=[{
                            "source": "segment",
                            "name": segment.get('name', '')
                        }]
                    )
                    chunks_count += 1

            except Exception as e:
                logger.error(f"Error indexing segments: {e}")

        return chunks_count

    def _index_market_data(self, market_file: Path) -> int:
        """Index market fundamentals"""
        chunks_count = 0

        try:
            with open(market_file, 'r') as f:
                data = json.load(f)

            # Create text summary
            text = "Company Fundamentals:\n"
            for key, value in data.items():
                if value is not None:
                    text += f"{key}: {value}\n"

            chunk_id = "market_fundamentals"
            embedding = self.embeddings_model.encode(text).tolist()

            self.collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[{"source": "market_data"}]
            )
            chunks_count = 1

        except Exception as e:
            logger.error(f"Error indexing market data: {e}")

        return chunks_count

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        filter_source: Optional[str] = None
    ) -> List[Dict]:
        """
        Query the document collection

        Args:
            query_text: Question or search query
            n_results: Number of results to return
            filter_source: Optional source filter (e.g., "sec_filing", "management")

        Returns:
            List of relevant document chunks with metadata
        """
        if not self.available:
            logger.error("RAG system not available")
            return []

        # Generate query embedding
        query_embedding = self.embeddings_model.encode(query_text).tolist()

        # Query collection
        where_filter = {"source": filter_source} if filter_source else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter
        )

        # Format results
        formatted_results = []
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                formatted_results.append({
                    'text': doc,
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })

        return formatted_results

    def get_context_for_query(
        self,
        query: str,
        n_results: int = 5
    ) -> str:
        """
        Get formatted context for a query

        Args:
            query: User's question
            n_results: Number of context chunks to retrieve

        Returns:
            Formatted context string
        """
        results = self.query(query, n_results=n_results)

        if not results:
            return "No relevant context found."

        context = "Relevant Context:\n\n"
        for i, result in enumerate(results, 1):
            context += f"[Source {i}: {result['metadata'].get('source', 'unknown')}]\n"
            context += f"{result['text']}\n\n"

        return context
