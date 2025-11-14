"""
Report Generator using RAG and local LLM
Generates detailed initiating coverage reports
"""
from pathlib import Path
from typing import Optional, Dict, List
import logging
import json
from datetime import datetime

from .rag_system import RAGSystem

logger = logging.getLogger(__name__)

# Optional Ollama support
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("ollama not available - report generation will be disabled")


class ReportGenerator:
    """Generate equity research reports using RAG + LLM"""

    def __init__(
        self,
        data_dir: Path,
        ticker: str,
        model_name: str = "llama3.1:8b"
    ):
        """
        Initialize report generator

        Args:
            data_dir: Path to data directory
            ticker: Stock ticker
            model_name: Ollama model name (default: llama3.1:8b)
        """
        self.data_dir = data_dir
        self.ticker = ticker
        self.model_name = model_name

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

        logger.info(f"Report generator initialized with model: {model_name}")

    def generate_initiating_coverage_report(
        self,
        progress_callback: Optional[callable] = None
    ) -> Optional[str]:
        """
        Generate a comprehensive initiating coverage report

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            Generated report as markdown string
        """
        if not self.available:
            logger.error("Report generator not available")
            return None

        if progress_callback:
            progress_callback("Generating initiating coverage report...")

        # Collect context from different sources
        contexts = self._gather_report_contexts()

        # Generate each section
        sections = []

        # 1. Executive Summary
        if progress_callback:
            progress_callback("Generating executive summary...")
        exec_summary = self._generate_executive_summary(contexts)
        sections.append(("Executive Summary", exec_summary))

        # 2. Company Overview
        if progress_callback:
            progress_callback("Generating company overview...")
        company_overview = self._generate_company_overview(contexts)
        sections.append(("Company Overview", company_overview))

        # 3. Business Segments
        if progress_callback:
            progress_callback("Analyzing business segments...")
        segments_analysis = self._generate_segments_analysis(contexts)
        sections.append(("Business Segments", segments_analysis))

        # 4. Management Analysis
        if progress_callback:
            progress_callback("Analyzing management team...")
        management_analysis = self._generate_management_analysis(contexts)
        sections.append(("Management Team", management_analysis))

        # 5. Financial Analysis
        if progress_callback:
            progress_callback("Analyzing financials...")
        financial_analysis = self._generate_financial_analysis(contexts)
        sections.append(("Financial Analysis", financial_analysis))

        # 6. Investment Thesis
        if progress_callback:
            progress_callback("Formulating investment thesis...")
        investment_thesis = self._generate_investment_thesis(contexts)
        sections.append(("Investment Thesis", investment_thesis))

        # 7. Risks
        if progress_callback:
            progress_callback("Identifying risks...")
        risks = self._generate_risks_section(contexts)
        sections.append(("Key Risks", risks))

        # Compile full report
        report = self._compile_report(sections)

        if progress_callback:
            progress_callback("Report generation complete!")

        return report

    def _gather_report_contexts(self) -> Dict[str, str]:
        """Gather relevant context from all sources"""
        contexts = {}

        # Company fundamentals
        contexts['fundamentals'] = self.rag.get_context_for_query(
            "What are the company's key financial metrics and fundamentals?",
            n_results=3
        )

        # Business model
        contexts['business_model'] = self.rag.get_context_for_query(
            "What is the company's business model and how do they make money?",
            n_results=5
        )

        # Segments
        contexts['segments'] = self.rag.get_context_for_query(
            "What are the company's business segments and product lines?",
            n_results=5
        )

        # Management
        contexts['management'] = self.rag.get_context_for_query(
            "Who are the key executives and board members?",
            n_results=5
        )

        # Strategy
        contexts['strategy'] = self.rag.get_context_for_query(
            "What is the company's strategy and future direction?",
            n_results=5
        )

        # Recent developments
        contexts['recent'] = self.rag.get_context_for_query(
            "What are the most recent company developments and news?",
            n_results=5
        )

        return contexts

    def _generate_executive_summary(self, contexts: Dict[str, str]) -> str:
        """Generate executive summary section"""
        prompt = f"""You are an equity research analyst writing an initiating coverage report for {self.ticker}.

Based on the following context, write a compelling executive summary (2-3 paragraphs) that:
1. Provides a brief company overview
2. Highlights the key investment thesis
3. Mentions the primary strengths and opportunities
4. Notes major risks briefly

Context:
{contexts.get('business_model', '')}
{contexts.get('fundamentals', '')}

Write a professional, concise executive summary:"""

        return self._call_llm(prompt)

    def _generate_company_overview(self, contexts: Dict[str, str]) -> str:
        """Generate company overview section"""
        prompt = f"""You are an equity research analyst writing about {self.ticker}.

Based on the following context, write a detailed company overview that covers:
1. What the company does (products/services)
2. Target markets and customers
3. Competitive positioning
4. Brief history and evolution

Context:
{contexts.get('business_model', '')}

Write a comprehensive company overview (3-4 paragraphs):"""

        return self._call_llm(prompt)

    def _generate_segments_analysis(self, contexts: Dict[str, str]) -> str:
        """Generate business segments analysis"""
        prompt = f"""You are an equity research analyst analyzing {self.ticker}'s business segments.

Based on the following context, analyze the company's business segments:
1. List each major segment
2. Describe what each segment does
3. Assess the growth potential of each segment
4. Note any segment-specific trends or challenges

Context:
{contexts.get('segments', '')}

Provide detailed segment analysis:"""

        return self._call_llm(prompt)

    def _generate_management_analysis(self, contexts: Dict[str, str]) -> str:
        """Generate management team analysis"""
        prompt = f"""You are an equity research analyst evaluating {self.ticker}'s management team.

Based on the following context, analyze the management team:
1. Identify key executives and their roles
2. Assess their experience and track record
3. Note any governance considerations
4. Evaluate the overall strength of the leadership

Context:
{contexts.get('management', '')}

Provide management team analysis:"""

        return self._call_llm(prompt)

    def _generate_financial_analysis(self, contexts: Dict[str, str]) -> str:
        """Generate financial analysis section"""
        prompt = f"""You are an equity research analyst analyzing {self.ticker}'s financials.

Based on the following financial data, provide analysis covering:
1. Revenue trends and growth rates
2. Profitability metrics (margins, returns)
3. Balance sheet strength
4. Cash flow characteristics
5. Key financial trends

Context:
{contexts.get('fundamentals', '')}

Provide comprehensive financial analysis:"""

        return self._call_llm(prompt)

    def _generate_investment_thesis(self, contexts: Dict[str, str]) -> str:
        """Generate investment thesis"""
        prompt = f"""You are an equity research analyst formulating an investment thesis for {self.ticker}.

Based on all available context, create a compelling investment thesis that:
1. Identifies 3-5 key investment positives (bull case)
2. Explains why these factors make the company attractive
3. Discusses catalysts that could drive value
4. Provides a balanced perspective

Context:
Business Model: {contexts.get('business_model', '')}
Strategy: {contexts.get('strategy', '')}
Fundamentals: {contexts.get('fundamentals', '')}

Write a clear investment thesis:"""

        return self._call_llm(prompt)

    def _generate_risks_section(self, contexts: Dict[str, str]) -> str:
        """Generate risks section"""
        prompt = f"""You are an equity research analyst identifying risks for {self.ticker}.

Based on the available context, identify and explain key risks:
1. Company-specific operational risks
2. Market and competitive risks
3. Financial risks
4. Regulatory or legal risks
5. Other material risks

Context:
{contexts.get('business_model', '')}
{contexts.get('recent', '')}

Identify and explain key risks (5-7 major risks):"""

        return self._call_llm(prompt)

    def _call_llm(self, prompt: str, max_tokens: int = 1000) -> str:
        """
        Call the LLM with a prompt

        Args:
            prompt: The prompt to send
            max_tokens: Maximum response length

        Returns:
            Generated text
        """
        try:
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    'num_predict': max_tokens,
                    'temperature': 0.7,
                }
            )
            return response['response']

        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return f"[Error generating content: {str(e)}]"

    def _compile_report(self, sections: List[tuple]) -> str:
        """
        Compile all sections into a final report

        Args:
            sections: List of (title, content) tuples

        Returns:
            Complete markdown report
        """
        # Header
        report = f"""# Initiating Coverage Report: {self.ticker}

**Generated:** {datetime.now().strftime('%B %d, %Y')}
**Analyst:** AI Research System

---

"""

        # Add each section
        for title, content in sections:
            report += f"## {title}\n\n"
            report += f"{content}\n\n"
            report += "---\n\n"

        # Footer
        report += """
## Disclaimers

This report is generated using automated analysis and should not be considered investment advice.
Please conduct your own due diligence and consult with qualified financial advisors before making
investment decisions.

"""

        return report

    def save_report(self, report: str, output_path: Optional[Path] = None) -> Path:
        """
        Save report to file

        Args:
            report: Report content
            output_path: Optional custom output path

        Returns:
            Path where report was saved
        """
        if output_path is None:
            output_path = self.data_dir / f"{self.ticker}_initiating_coverage_report.md"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"Report saved to {output_path}")
        return output_path
