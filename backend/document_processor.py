"""
Document Processor Module - FAISS Version
Handles PDF loading, text extraction, and chunking for RAG system.
"""

from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
import os
from typing import List
from langchain.schema import Document


class DocumentProcessor:
    """
    Processes documents for RAG system using FAISS vector store.
    
    Features:
    - PDF loading and text extraction
    - Text chunking with overlap
    - Embedding generation
    - FAISS vector store creation and management
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        """
        Initialize the document processor.
        
        Args:
            chunk_size: Size of text chunks in characters (default: 1000)
            chunk_overlap: Overlap between chunks in characters (default: 200)
            embedding_model: HuggingFace model name for embeddings
        """
        print("🔧 Initializing Document Processor with FAISS...")
        
        # Initialize embeddings model
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={'device': 'cpu'},  # Use 'cuda' if you have GPU
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        print("✅ Document Processor ready!")
    
    def load_pdf(self, pdf_path: str) -> List[Document]:
        """
        Load a PDF file and extract text.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of Document objects with page content
            
        Raises:
            FileNotFoundError: If PDF file doesn't exist
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        print(f"📄 Loading PDF: {os.path.basename(pdf_path)}")
        
        try:
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()
            print(f"✅ Loaded {len(documents)} pages from PDF")
            return documents
        except Exception as e:
            print(f"❌ Error loading PDF: {str(e)}")
            raise
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """
        Split documents into smaller chunks for better retrieval.
        
        Args:
            documents: List of Document objects
            
        Returns:
            List of chunked Document objects
        """
        print(f"✂️  Chunking {len(documents)} documents...")
        
        chunks = self.text_splitter.split_documents(documents)
        
        print(f"✅ Created {len(chunks)} chunks")
        print(f"   Average chunk size: {sum(len(c.page_content) for c in chunks) / len(chunks):.0f} characters")
        
        return chunks
    
    def process_pdf(self, pdf_path: str) -> List[Document]:
        """
        Complete pipeline: load PDF and chunk it.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of chunked Document objects
        """
        print(f"\n{'='*60}")
        print(f"Processing: {os.path.basename(pdf_path)}")
        print(f"{'='*60}")
        
        documents = self.load_pdf(pdf_path)
        chunks = self.chunk_documents(documents)
        
        print(f"{'='*60}\n")
        
        return chunks
    
    def create_vector_store(
        self,
        chunks: List[Document],
        persist_directory: str = "./data/vector_store"
    ) -> FAISS:
        """
        Create a FAISS vector store from document chunks.
        
        Args:
            chunks: List of document chunks
            persist_directory: Directory to save the vector store
            
        Returns:
            FAISS vector store instance
        """
        print(f"🔮 Creating FAISS vector store with {len(chunks)} chunks...")
        print("   This may take a minute for first-time embedding model download...")
        
        # Create directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        try:
            # Create FAISS vector store
            vectorstore = FAISS.from_documents(
                documents=chunks,
                embedding=self.embeddings
            )
            
            # Save to disk
            vectorstore.save_local(persist_directory)
            
            print(f"✅ Vector store created and saved to: {persist_directory}")
            print(f"   Total vectors: {vectorstore.index.ntotal}")
            
            return vectorstore
            
        except Exception as e:
            print(f"❌ Error creating vector store: {str(e)}")
            raise
    
    def load_vector_store(
        self,
        persist_directory: str = "./data/vector_store"
    ) -> FAISS:
        """
        Load an existing FAISS vector store from disk.
        
        Args:
            persist_directory: Directory where vector store is saved
            
        Returns:
            FAISS vector store instance
            
        Raises:
            FileNotFoundError: If vector store doesn't exist
        """
        if not os.path.exists(persist_directory):
            raise FileNotFoundError(
                f"Vector store not found at: {persist_directory}\n"
                f"Please create one first by processing documents."
            )
        
        print(f"📂 Loading FAISS vector store from: {persist_directory}")
        
        try:
            vectorstore = FAISS.load_local(
                persist_directory,
                self.embeddings,
                allow_dangerous_deserialization=True  # Required for FAISS
            )
            
            print(f"✅ Vector store loaded successfully!")
            print(f"   Total vectors: {vectorstore.index.ntotal}")
            
            return vectorstore
            
        except Exception as e:
            print(f"❌ Error loading vector store: {str(e)}")
            raise
    
    def process_multiple_pdfs(
        self,
        pdf_paths: List[str],
        persist_directory: str = "./data/vector_store"
    ) -> FAISS:
        """
        Process multiple PDFs and create a single vector store.
        
        Args:
            pdf_paths: List of paths to PDF files
            persist_directory: Directory to save the vector store
            
        Returns:
            FAISS vector store instance
        """
        print(f"\n{'='*60}")
        print(f"Processing {len(pdf_paths)} PDF files")
        print(f"{'='*60}\n")
        
        all_chunks = []
        
        for i, pdf_path in enumerate(pdf_paths, 1):
            try:
                print(f"[{i}/{len(pdf_paths)}] Processing: {os.path.basename(pdf_path)}")
                chunks = self.process_pdf(pdf_path)
                all_chunks.extend(chunks)
            except Exception as e:
                print(f"❌ Error processing {pdf_path}: {str(e)}")
                print("   Skipping this file and continuing...\n")
                continue
        
        if not all_chunks:
            raise ValueError("No documents were successfully processed")
        
        print(f"\n📊 Summary:")
        print(f"   Total PDFs processed: {len(pdf_paths)}")
        print(f"   Total chunks created: {len(all_chunks)}")
        print()
        
        return self.create_vector_store(all_chunks, persist_directory)
    
    def search_similar(
        self,
        vectorstore: FAISS,
        query: str,
        k: int = 3
    ) -> List[Document]:
        """
        Search for similar documents in the vector store.
        
        Args:
            vectorstore: FAISS vector store instance
            query: Search query
            k: Number of results to return
            
        Returns:
            List of similar documents
        """
        print(f"🔍 Searching for: '{query}'")
        print(f"   Retrieving top {k} results...")
        
        results = vectorstore.similarity_search(query, k=k)
        
        print(f"✅ Found {len(results)} similar chunks")
        
        return results


# Example usage and testing
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 Document Processor - Test Mode")
    print("="*60 + "\n")
    
    # Initialize processor
    processor = DocumentProcessor()
    
    print("\n📝 Instructions:")
    print("   To test with a real PDF:")
    print("   1. Place a PDF in ./data/uploaded_files/")
    print("   2. Update the path below")
    print("   3. Run: python backend/document_processor.py")
    print()
    
    # Example test (uncomment when you have a PDF)
    # pdf_path = "./data/uploaded_files/sample.pdf"
    # chunks = processor.process_pdf(pdf_path)
    # vectorstore = processor.create_vector_store(chunks)
    # 
    # # Test search
    # results = processor.search_similar(vectorstore, "What is machine learning?")
    # for i, doc in enumerate(results, 1):
    #     print(f"\nResult {i}:")
    #     print(doc.page_content[:200] + "...")
    
    print("✅ Document Processor module is ready!")
    print("="*60 + "\n")