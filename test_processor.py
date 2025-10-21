"""
Test Document Processor - FAISS Version
Basic functionality tests without requiring a PDF
"""

from backend.document_processor import DocumentProcessor
from langchain.schema import Document


def test_initialization():
    """Test that processor initializes correctly"""
    print("\n" + "="*60)
    print("Test 1: Initialization")
    print("="*60)
    
    try:
        processor = DocumentProcessor()
        print("✅ PASSED: Processor initialized successfully!")
        return processor
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        raise


def test_embeddings(processor):
    """Test that embeddings work"""
    print("\n" + "="*60)
    print("Test 2: Embeddings Generation")
    print("="*60)
    
    try:
        test_text = "This is a test sentence about machine learning and artificial intelligence."
        print(f"Test text: '{test_text}'")
        print("Generating embedding...")
        
        embedding = processor.embeddings.embed_query(test_text)
        
        print(f"✅ PASSED: Created embedding with {len(embedding)} dimensions")
        print(f"   First 5 values: [{', '.join([f'{x:.3f}' for x in embedding[:5]])}]")
        print(f"   Embedding range: [{min(embedding):.3f}, {max(embedding):.3f}]")
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        raise


def test_text_splitting(processor):
    """Test text splitting"""
    print("\n" + "="*60)
    print("Test 3: Text Splitting")
    print("="*60)
    
    try:
        # Create a long text
        long_text = """
        Machine learning is a subset of artificial intelligence. 
        It focuses on developing systems that can learn from data.
        Deep learning uses neural networks with multiple layers.
        Natural language processing helps computers understand human language.
        Computer vision enables machines to interpret visual information.
        Reinforcement learning trains agents through rewards and penalties.
        """ * 20  # Repeat to make it long enough to split
        
        print(f"Original text length: {len(long_text)} characters")
        
        # Create document
        doc = Document(page_content=long_text, metadata={"source": "test"})
        
        # Split into chunks
        chunks = processor.chunk_documents([doc])
        
        print(f"✅ PASSED: Split text into {len(chunks)} chunks")
        print(f"   Chunk size range: {min(len(c.page_content) for c in chunks)} - {max(len(c.page_content) for c in chunks)} chars")
        print(f"   Average chunk size: {sum(len(c.page_content) for c in chunks) / len(chunks):.0f} chars")
        
        # Show first chunk preview
        print(f"\n   First chunk preview:")
        print(f"   '{chunks[0].page_content[:100]}...'")
        
        return chunks
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        raise


def test_vector_store_creation(processor, chunks):
    """Test vector store creation and search"""
    print("\n" + "="*60)
    print("Test 4: Vector Store Creation")
    print("="*60)
    
    try:
        import tempfile
        import shutil
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        print(f"Using temporary directory: {temp_dir}")
        
        # Create vector store
        vectorstore = processor.create_vector_store(chunks, persist_directory=temp_dir)
        
        print(f"✅ PASSED: Vector store created successfully")
        
        # Test search
        print("\n   Testing similarity search...")
        test_query = "What is machine learning?"
        results = processor.search_similar(vectorstore, test_query, k=2)
        
        print(f"   Query: '{test_query}'")
        print(f"   Found {len(results)} results")
        
        for i, result in enumerate(results, 1):
            print(f"\n   Result {i}:")
            print(f"   {result.page_content[:100]}...")
        
        # Clean up
        shutil.rmtree(temp_dir)
        print(f"\n   Cleaned up temporary directory")
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        raise


def test_multiple_documents(processor):
    """Test processing multiple documents"""
    print("\n" + "="*60)
    print("Test 5: Multiple Documents Processing")
    print("="*60)
    
    try:
        # Create multiple test documents
        docs = [
            Document(
                page_content="Python is a high-level programming language. " * 50,
                metadata={"source": "python.txt"}
            ),
            Document(
                page_content="JavaScript is used for web development. " * 50,
                metadata={"source": "javascript.txt"}
            ),
            Document(
                page_content="Machine learning requires mathematical foundations. " * 50,
                metadata={"source": "ml.txt"}
            )
        ]
        
        print(f"Processing {len(docs)} test documents...")
        
        # Chunk all documents
        all_chunks = []
        for doc in docs:
            chunks = processor.chunk_documents([doc])
            all_chunks.extend(chunks)
        
        print(f"✅ PASSED: Processed {len(docs)} documents into {len(all_chunks)} chunks")
        
        return all_chunks
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        raise


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧪 DOCUMENT PROCESSOR TEST SUITE - FAISS VERSION")
    print("="*70)
    
    try:
        # Test 1: Initialization
        processor = test_initialization()
        
        # Test 2: Embeddings
        test_embeddings(processor)
        
        # Test 3: Text splitting
        chunks = test_text_splitting(processor)
        
        # Test 4: Vector store
        test_vector_store_creation(processor, chunks)
        
        # Test 5: Multiple documents
        multi_chunks = test_multiple_documents(processor)
        
        # Final summary
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\n📋 Summary:")
        print(f"   ✓ Processor initialization")
        print(f"   ✓ Embedding generation")
        print(f"   ✓ Text chunking")
        print(f"   ✓ Vector store creation and search")
        print(f"   ✓ Multiple document processing")
        print("\n🎉 Document Processor is working correctly!")
        print("="*70 + "\n")
        
        return True
        
    except Exception as e:
        print("\n" + "="*70)
        print("❌ TEST SUITE FAILED")
        print("="*70)
        print(f"\nError: {str(e)}")
        print("\n" + "="*70 + "\n")
        
        import traceback
        traceback.print_exc()
        
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
