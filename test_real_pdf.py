"""
Test Document Processor with Real PDF
"""

import os
from backend.document_processor import DocumentProcessor


def find_pdf_files():
    """Find all PDFs in the uploaded_files directory"""
    pdf_dir = "./data/uploaded_files"
    
    if not os.path.exists(pdf_dir):
        print(f"❌ Directory not found: {pdf_dir}")
        return []
    
    pdf_files = [
        os.path.join(pdf_dir, f) 
        for f in os.listdir(pdf_dir) 
        if f.endswith('.pdf')
    ]
    
    return pdf_files


def test_single_pdf(pdf_path):
    """Test processing a single PDF"""
    print("\n" + "="*70)
    print("🧪 TESTING WITH REAL PDF")
    print("="*70)
    
    print(f"\n📄 PDF: {os.path.basename(pdf_path)}")
    print(f"   Size: {os.path.getsize(pdf_path) / 1024:.1f} KB")
    
    # Initialize processor
    processor = DocumentProcessor()
    
    # Process PDF
    print("\n" + "-"*70)
    chunks = processor.process_pdf(pdf_path)
    print("-"*70)
    
    # Show sample chunks
    print(f"\n📊 Chunk Analysis:")
    print(f"   Total chunks: {len(chunks)}")
    
    chunk_lengths = [len(c.page_content) for c in chunks]
    print(f"   Avg length: {sum(chunk_lengths) / len(chunks):.0f} chars")
    print(f"   Min length: {min(chunk_lengths)} chars")
    print(f"   Max length: {max(chunk_lengths)} chars")
    
    # Display first few chunks
    print(f"\n📝 Sample Chunks:")
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"\n   Chunk {i}:")
        print(f"   {'-'*60}")
        print(f"   {chunk.page_content[:200]}...")
        print(f"   Metadata: {chunk.metadata}")
    
    return chunks, processor


def test_vector_store_creation(chunks, processor):
    """Create vector store and test search"""
    print("\n" + "="*70)
    print("🔮 CREATING VECTOR STORE")
    print("="*70)
    
    # Create vector store
    persist_dir = "./data/vector_store"
    vectorstore = processor.create_vector_store(chunks, persist_dir)
    
    print(f"\n✅ Vector store created successfully!")
    
    return vectorstore


def test_semantic_search(vectorstore, processor):
    """Test semantic search with various queries"""
    print("\n" + "="*70)
    print("🔍 TESTING SEMANTIC SEARCH")
    print("="*70)
    
    # Test queries
    test_queries = [
        "What are the main concepts explained?",
        "How does this work?",
        "What are the key definitions?",
        "Explain the methodology",
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*70}")
        print(f"Query {i}: '{query}'")
        print(f"{'='*70}")
        
        results = processor.search_similar(vectorstore, query, k=2)
        
        for j, result in enumerate(results, 1):
            print(f"\n   Result {j}:")
            print(f"   {'-'*60}")
            print(f"   {result.page_content[:250]}...")
            print(f"   Source: {result.metadata}")
    
    # Interactive search
    print("\n" + "="*70)
    print("💬 INTERACTIVE SEARCH")
    print("="*70)
    print("Enter your questions (or 'quit' to exit)")
    
    while True:
        try:
            query = input("\n🔍 Your question: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                break
            
            if not query:
                continue
            
            results = processor.search_similar(vectorstore, query, k=3)
            
            print(f"\n📚 Top {len(results)} relevant chunks:\n")
            for i, result in enumerate(results, 1):
                print(f"{i}. {result.page_content[:150]}...")
                print(f"   [{result.metadata}]\n")
        
        except KeyboardInterrupt:
            break
    
    print("\n✅ Interactive search ended")


def main():
    """Main test function"""
    print("\n" + "="*70)
    print("📚 REAL PDF TESTING SUITE")
    print("="*70)
    
    # Find PDFs
    pdf_files = find_pdf_files()
    
    if not pdf_files:
        print("\n❌ No PDF files found in data/uploaded_files/")
        print("\n💡 To test with a PDF:")
        print("   1. Add a PDF to: data/uploaded_files/")
        print("   2. Run this script again")
        print("\n   Example:")
        print("   cp ~/Downloads/your_book.pdf data/uploaded_files/")
        return
    
    print(f"\n✅ Found {len(pdf_files)} PDF(s):")
    for i, pdf in enumerate(pdf_files, 1):
        print(f"   {i}. {os.path.basename(pdf)}")
    
    # Use first PDF
    pdf_path = pdf_files[0]
    
    try:
        # Test processing
        chunks, processor = test_single_pdf(pdf_path)
        
        # Create vector store
        vectorstore = test_vector_store_creation(chunks, processor)
        
        # Test search
        test_semantic_search(vectorstore, processor)
        
        print("\n" + "="*70)
        print("✅ ALL REAL PDF TESTS COMPLETED!")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
