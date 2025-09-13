#!/usr/bin/env python3
"""
Debug the add_vectors error
"""
import os
import asyncio
import tempfile
import traceback
from datetime import datetime

# Set threading controls BEFORE any imports
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

from backend.core.vector_database import PersistentVectorDatabase, VectorMetadata
import numpy as np

async def debug_add_vectors():
    """Debug the add_vectors method"""
    
    with tempfile.TemporaryDirectory(prefix="debug_vector_db_") as temp_dir:
        print(f"Using test directory: {temp_dir}")
        
        try:
            # Initialize database
            print("1. Initializing PersistentVectorDatabase...")
            db = PersistentVectorDatabase(temp_dir)
            await db.initialize()
            print("✅ Database initialized successfully")
            
            # Add embedding model
            print("2. Adding all-MiniLM-L6-v2 embedding model...")
            await db.add_embedding_model("all-MiniLM-L6-v2")
            print("✅ Embedding model added successfully")
            
            # Create test data with VectorMetadata objects (like distributed database does)
            print("3. Creating test data...")
            embeddings = [
                np.random.rand(384).astype(np.float32),
                np.random.rand(384).astype(np.float32)
            ]
            
            metadata = [
                VectorMetadata(
                    id="test_vector_1",
                    text="This is test vector 1",
                    embedding_model="all-MiniLM-L6-v2",
                    timestamp=datetime.now(),
                    content_hash="hash1",
                    metadata={"source": "test"}
                ),
                VectorMetadata(
                    id="test_vector_2", 
                    text="This is test vector 2",
                    embedding_model="all-MiniLM-L6-v2",
                    timestamp=datetime.now(),
                    content_hash="hash2",
                    metadata={"source": "test"}
                )
            ]
            print("✅ Test data created")
            
            # Test add_vectors
            print("4. Testing add_vectors...")
            result = await db.add_vectors(
                embeddings=embeddings,
                metadata=metadata,
                model_name="all-MiniLM-L6-v2"
            )
            print(f"✅ add_vectors completed: {result}")
            
        except Exception as e:
            print(f"❌ Error occurred: {type(e).__name__}: {e}")
            print("Full traceback:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_add_vectors())
