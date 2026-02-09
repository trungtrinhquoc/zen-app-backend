"""
Test script for Memory System
Run this to verify everything is working
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import getDbSession
from app.services.embedding_service import createEmbedding
from app.modules.memory.service import MemoryService
from uuid import UUID


async def test_embedding():
    """Test 1: Embedding generation"""
    print("\n" + "="*60)
    print("TEST 1: Embedding Generation")
    print("="*60)
    
    try:
        text = "Tôi cảm thấy lo lắng về công việc"
        embedding = await createEmbedding(text)
        
        print(f"✅ Embedding created successfully!")
        print(f"   Dimensions: {len(embedding)}")
        print(f"   First 5 values: {embedding[:5]}")
        print(f"   Text: {text}")
        return True
    except Exception as e:
        print(f"❌ Embedding test failed: {e}")
        return False


async def test_memory_save():
    """Test 2: Save semantic memory"""
    print("\n" + "="*60)
    print("TEST 2: Save Semantic Memory")
    print("="*60)
    
    try:
        async for db in getDbSession():
            service = MemoryService(db)
            
            # Use existing user ID from your database
            userId = UUID("25f1e353-566d-4ef2-8927-32c9fddada42")
            
            memory = await service.saveSemanticMemory(
                userId=userId,
                conversationId=None,
                content="User đã chia sẻ về stress công việc và deadline",
                memoryType="conversation",
                emotionalContext={"emotion": "anxious", "energy": 3},
                tags=["work", "stress"],
                importanceScore=0.7
            )
            
            print(f"✅ Memory saved successfully!")
            print(f"   ID: {memory.id}")
            print(f"   Content: {memory.content}")
            print(f"   Type: {memory.memory_type}")
            print(f"   Importance: {memory.importance_score}")
            
            return True
    except Exception as e:
        print(f"❌ Memory save test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_memory_search():
    """Test 3: Semantic search"""
    print("\n" + "="*60)
    print("TEST 3: Semantic Memory Search")
    print("="*60)
    
    try:
        async for db in getDbSession():
            service = MemoryService(db)
            
            userId = UUID("25f1e353-566d-4ef2-8927-32c9fddada42")
            
            memories = await service.searchSemanticMemories(
                userId=userId,
                query="Tôi lại stress về công việc",
                limit=3,
                minImportance=0.3,
                minSimilarity=0.7
            )
            
            print(f"✅ Search completed!")
            print(f"   Found {len(memories)} relevant memories")
            
            for i, mem in enumerate(memories, 1):
                print(f"\n   Memory {i}:")
                print(f"   - Content: {mem['content']}")
                print(f"   - Similarity: {mem['similarity']}")
                print(f"   - Importance: {mem['importance']}")
                print(f"   - Type: {mem['memory_type']}")
            
            return True
    except Exception as e:
        print(f"❌ Memory search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 MEMORY SYSTEM TEST SUITE")
    print("="*60)
    
    results = []
    
    # Test 1: Embedding
    results.append(await test_embedding())
    
    # Test 2: Save memory
    results.append(await test_memory_save())
    
    # Test 3: Search memory
    results.append(await test_memory_search())
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
