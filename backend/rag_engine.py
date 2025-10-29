"""
RAG Engine Module
Handles retrieval-augmented generation for question answering.
"""

from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from typing import List, Dict
import os


class RAGEngine:
    """
    Retrieval-Augmented Generation Engine.
    
    Combines vector search with LLM generation for answering questions
    based on provided documents.
    """
    
    def __init__(
        self,
        vector_store_path: str = "./data/vector_store",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        """
        Initialize the RAG engine.
        
        Args:
            vector_store_path: Path to the FAISS vector store
            embedding_model: Name of the embedding model
        """
        print("🚀 Initializing RAG Engine...")
        
        self.vector_store_path = vector_store_path
        
        # Initialize embeddings (same as document processor)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # Load vector store
        self.vectorstore = self._load_vector_store()
        
        # Define prompt template
        self.prompt_template = self._create_prompt_template()
        
        print("✅ RAG Engine ready!")
    
    def _load_vector_store(self) -> FAISS:
        """Load the FAISS vector store"""
        if not os.path.exists(self.vector_store_path):
            raise FileNotFoundError(
                f"Vector store not found at: {self.vector_store_path}\n"
                f"Please process documents first using DocumentProcessor."
            )
        
        print(f"📂 Loading vector store from: {self.vector_store_path}")
        
        vectorstore = FAISS.load_local(
            self.vector_store_path,
            self.embeddings,
            allow_dangerous_deserialization=True
        )
        
        print(f"✅ Vector store loaded ({vectorstore.index.ntotal} vectors)")
        return vectorstore
    
    def _create_prompt_template(self) -> PromptTemplate:
        """Create the prompt template for the LLM"""
        template = """You are a helpful Computer Science tutor. Answer the question based ONLY on the context provided below.

Context:
{context}

Question: {question}

Instructions:
1. Answer clearly and concisely
2. Use ONLY information from the context
3. If the context doesn't contain enough information, say "I don't have enough information in the provided documents to answer this question."
4. Cite specific parts of the context when possible

Answer:"""
        
        return PromptTemplate(
            template=template,
            input_variables=["context", "question"]
        )
    
    def retrieve_context(self, query: str, k: int = 3) -> List[Dict]:
        """
        Retrieve relevant context chunks for a query.
        
        Args:
            query: User's question
            k: Number of chunks to retrieve
            
        Returns:
            List of relevant document chunks with metadata
        """
        print(f"🔍 Retrieving context for: '{query}'")
        
        # Search vector store
        results = self.vectorstore.similarity_search_with_score(query, k=k)
        
        # Format results
        context_chunks = []
        for doc, score in results:
            context_chunks.append({
                'content': doc.page_content,
                'metadata': doc.metadata,
                'score': float(score)
            })
        
        print(f"✅ Retrieved {len(context_chunks)} relevant chunks")
        
        return context_chunks
    
    def format_context(self, context_chunks: List[Dict]) -> str:
        """
        Format retrieved chunks into a single context string.
        
        Args:
            context_chunks: List of context dictionaries
            
        Returns:
            Formatted context string
        """
        formatted_parts = []
        
        for i, chunk in enumerate(context_chunks, 1):
            source = chunk['metadata'].get('source', 'Unknown')
            page = chunk['metadata'].get('page', 'N/A')
            
            formatted_parts.append(
                f"[Source {i} - {os.path.basename(source)}, Page {page}]\n"
                f"{chunk['content']}\n"
            )
        
        return "\n".join(formatted_parts)
    
    def generate_prompt(self, query: str, context_chunks: List[Dict]) -> str:
        """
        Generate the full prompt to send to LLM.
        
        Args:
            query: User's question
            context_chunks: Retrieved context
            
        Returns:
            Formatted prompt string
        """
        context = self.format_context(context_chunks)
        prompt = self.prompt_template.format(
            context=context,
            question=query
        )
        
        return prompt
    
    def query(
        self,
        question: str,
        k: int = 3,
        return_context: bool = True
    ) -> Dict:
        """
        Main query method - retrieve context and prepare for LLM.
        
        Args:
            question: User's question
            k: Number of context chunks to retrieve
            return_context: Whether to return retrieved context
            
        Returns:
            Dictionary with prompt and context information
        """
        print(f"\n{'='*70}")
        print(f"❓ Question: {question}")
        print(f"{'='*70}")
        
        # Retrieve relevant context
        context_chunks = self.retrieve_context(question, k=k)
        
        # Generate prompt
        prompt = self.generate_prompt(question, context_chunks)
        
        # Prepare response
        response = {
            'question': question,
            'prompt': prompt,
            'num_chunks': len(context_chunks)
        }
        
        if return_context:
            response['context_chunks'] = context_chunks
        
        print(f"✅ Generated prompt ({len(prompt)} chars)")
        print(f"{'='*70}\n")
        
        return response
    
    def answer_question(self, question: str, k: int = 3) -> Dict:
        """
        Answer a question using RAG (without actual LLM for now).
        
        This method prepares everything needed for an LLM.
        In Week 3, we'll add actual LLM integration.
        
        Args:
            question: User's question
            k: Number of context chunks to retrieve
            
        Returns:
            Dictionary with question, context, and prompt
        """
        result = self.query(question, k=k, return_context=True)
        
        # For now, we return the prepared prompt
        # Later, we'll send this to Ollama/LLM
        print("💡 Note: LLM integration coming in Week 3")
        print("   For now, showing retrieved context and prepared prompt\n")
        
        return result


# Test the RAG engine
if __name__ == "__main__":
    print("\n" + "="*70)
    print("🧪 RAG ENGINE - TEST MODE")
    print("="*70 + "\n")
    
    try:
        # Initialize engine
        engine = RAGEngine()
        
        # Test query
        test_question = "What are the main concepts explained in the document?"
        result = engine.answer_question(test_question)
        
        # Display results
        print("\n" + "="*70)
        print("📊 QUERY RESULTS")
        print("="*70)
        
        print(f"\n❓ Question: {result['question']}")
        print(f"\n📚 Retrieved {result['num_chunks']} context chunks:")
        
        for i, chunk in enumerate(result['context_chunks'], 1):
            print(f"\n{i}. Score: {chunk['score']:.4f}")
            print(f"   {chunk['content'][:150]}...")
        
        print("\n" + "="*70)
        print("📝 GENERATED PROMPT")
        print("="*70)
        print(f"\n{result['prompt'][:500]}...")
        
        print("\n" + "="*70)
        print("✅ RAG ENGINE TEST COMPLETED")
        print("="*70 + "\n")
        
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        print("\n💡 To test the RAG engine:")
        print("   1. First run: python test_real_pdf.py")
        print("   2. Then run: python backend/rag_engine.py\n")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
