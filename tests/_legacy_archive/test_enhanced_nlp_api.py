#!/usr/bin/env python3
"""
API test for the Enhanced NLP Knowledge Pipeline
Tests the knowledge import endpoints with the new enhanced processing
"""

import asyncio
import aiohttp
import json
import time
import sys
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000"
WEBSOCKET_URL = "ws://localhost:8000/ws/cognitive-stream"

class KnowledgeImportAPITester:
    """Test the knowledge import API endpoints"""
    
    def __init__(self):
        self.session = None
        self.websocket = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def test_health_check(self):
        """Test if the API server is running"""
        print("1. Testing API Health Check...")
        try:
            async with self.session.get(f"{API_BASE_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ API server is healthy")
                    print(f"   Status: {data.get('status', 'unknown')}")
                    return True
                else:
                    print(f"❌ Health check failed: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Cannot connect to API server: {e}")
            return False
    
    async def test_knowledge_import_text(self):
        """Test text-based knowledge import"""
        print("\n2. Testing Text Knowledge Import...")
        
        # Sample text document
        test_content = """
        The field of quantum computing represents a revolutionary approach to computation that leverages quantum mechanical phenomena 
        such as superposition and entanglement. Unlike classical computers that use bits representing either 0 or 1, quantum computers 
        use quantum bits or qubits that can exist in superposition states.
        
        Key quantum algorithms include Shor's algorithm for factoring large numbers and Grover's algorithm for searching unsorted databases. 
        These algorithms demonstrate quantum supremacy in specific computational tasks.
        
        Major technology companies like IBM, Google, and Microsoft are investing heavily in quantum computing research. 
        Google claimed to achieve quantum supremacy in 2019 with their Sycamore processor.
        
        Quantum error correction remains a significant challenge due to quantum decoherence and environmental noise affecting qubit stability.
        """
        
        # Prepare the import request
        import_data = {
            "content": test_content,
            "title": "Quantum Computing Overview",
            "format_type": "plain"
        }
        
        try:
            print("   Sending import request...")
            async with self.session.post(
                f"{API_BASE_URL}/api/knowledge/import/text",
                json=import_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    print("✅ Text import successful")
                    
                    # Display results
                    print(f"   Import ID: {result.get('import_id', 'N/A')}")
                    print(f"   Status: {result.get('status', 'N/A')}")
                    
                    if 'processing_results' in result:
                        results = result['processing_results']
                        print(f"   Entities: {len(results.get('entities', []))}")
                        print(f"   Relations: {len(results.get('relations', []))}")
                        print(f"   Categories: {len(results.get('categories', []))}")
                        print(f"   Embeddings: {len(results.get('embeddings', []))}")
                    
                    return result.get('import_id')
                    
                elif response.status == 422:
                    error_data = await response.json()
                    print(f"❌ Validation error: {error_data}")
                    return None
                else:
                    error_text = await response.text()
                    print(f"❌ Import failed: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            print(f"❌ Import request failed: {e}")
            return None
    
    async def test_knowledge_import_file(self):
        """Test file-based knowledge import with a real PDF"""
        print("\n3. Testing File Knowledge Import with Real PDF...")
        
        # Use the existing GodelOS paper or download a substantial PDF
        pdf_file_path = Path("godelos_arxiv_paper_v2.pdf")
        
        if not pdf_file_path.exists():
            print("   GodelOS paper not found, using substantial text file instead...")
            # Use our comprehensive AI document
            pdf_file_path = Path("test_ai_comprehensive.txt")
            content_type = 'text/plain'
            file_type = 'text'
        else:
            print(f"   Found PDF: {pdf_file_path.name} ({pdf_file_path.stat().st_size / 1024:.1f} KB)")
            content_type = 'application/pdf'
            file_type = 'pdf'
        
        INTRODUCTION
        
        Artificial Intelligence (AI) represents one of the most transformative technological developments of the 21st century. 
        This field encompasses the creation of intelligent machines capable of performing tasks that typically require human 
        intelligence, including learning, reasoning, perception, and natural language understanding.
        
        HISTORICAL DEVELOPMENT
        
        The concept of artificial intelligence dates back to ancient mythology and philosophical discussions about the nature 
        of intelligence. However, the modern field of AI began in the 1950s with the work of pioneers such as Alan Turing, 
        who proposed the famous Turing Test as a measure of machine intelligence.
        
        Key milestones in AI development include:
        - 1950: Alan Turing publishes "Computing Machinery and Intelligence"
        - 1956: The Dartmouth Conference coins the term "Artificial Intelligence"
        - 1965: ELIZA, one of the first chatbots, is developed by Joseph Weizenbaum
        - 1997: IBM's Deep Blue defeats world chess champion Garry Kasparov
        - 2011: IBM Watson wins at Jeopardy!
        - 2016: Google's AlphaGo defeats world Go champion Lee Sedol
        - 2020: GPT-3 demonstrates remarkable natural language capabilities
        
        MACHINE LEARNING FUNDAMENTALS
        
        Machine Learning (ML) is a subset of artificial intelligence that focuses on algorithms and statistical models 
        that enable computer systems to improve their performance on a specific task through experience. Rather than 
        being explicitly programmed for every scenario, ML systems learn patterns from data.
        
        Types of Machine Learning:
        
        1. Supervised Learning
           - Uses labeled training data to learn input-output mappings
           - Examples: Classification, Regression
           - Algorithms: Linear Regression, Support Vector Machines, Random Forests
        
        2. Unsupervised Learning
           - Finds hidden patterns in data without labeled examples
           - Examples: Clustering, Dimensionality Reduction
           - Algorithms: K-means, Principal Component Analysis, DBSCAN
        
        3. Reinforcement Learning
           - Learns through interaction with an environment using rewards and penalties
           - Examples: Game playing, Robotics, Autonomous driving
           - Algorithms: Q-learning, Policy Gradient Methods, Actor-Critic
        
        DEEP LEARNING REVOLUTION
        
        Deep Learning represents a significant breakthrough in machine learning, utilizing artificial neural networks 
        with multiple layers to model and understand complex patterns in data. This approach has revolutionized fields 
        such as computer vision, natural language processing, and speech recognition.
        
        Key Deep Learning Architectures:
        
        1. Convolutional Neural Networks (CNNs)
           - Designed for processing grid-like data such as images
           - Applications: Image classification, object detection, medical imaging
           - Notable models: LeNet, AlexNet, ResNet, EfficientNet
        
        2. Recurrent Neural Networks (RNNs)
           - Designed for sequential data processing
           - Applications: Natural language processing, time series analysis
           - Variants: LSTM, GRU, Transformer architectures
        
        3. Generative Adversarial Networks (GANs)
           - Consist of two competing neural networks: generator and discriminator
           - Applications: Image generation, data augmentation, style transfer
           - Notable implementations: StyleGAN, CycleGAN, BigGAN
        
        NATURAL LANGUAGE PROCESSING
        
        Natural Language Processing (NLP) is a branch of AI that deals with the interaction between computers and 
        human language. Recent advances in NLP have been driven by transformer architectures and large language models.
        
        Key NLP Tasks:
        - Text Classification and Named Entity Recognition
        - Sentiment Analysis and Machine Translation
        - Question Answering and Text Summarization
        - Language Generation and Dialogue Systems
        
        Transformer Models:
        - BERT (Bidirectional Encoder Representations from Transformers)
        - GPT (Generative Pretrained Transformer) series
        - T5 (Text-to-Text Transfer Transformer)
        - PaLM (Pathways Language Model)
        
        CURRENT APPLICATIONS AND INDUSTRY IMPACT
        
        AI and ML technologies are now ubiquitous across various industries:
        
        Healthcare: Drug discovery, medical imaging, personalized treatment, epidemic modeling
        Finance: Algorithmic trading, fraud detection, credit scoring, regulatory compliance
        Technology: Search engines, recommendation systems, virtual assistants, cybersecurity
        Transportation: Autonomous vehicles, route optimization, predictive maintenance
        
        CONCLUSION
        
        Artificial Intelligence and Machine Learning represent transformative technologies that are reshaping our world. 
        As we advance toward more sophisticated AI systems, it is crucial to address the ethical, social, and economic 
        implications of these technologies while realizing their potential for human progress.
        """        """
        
        try:
            # Write test content to file
            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(test_content)
            
            # Prepare multipart form data
            data = aiohttp.FormData()
            data.add_field('file', open(test_file_path, 'rb'), filename='test_document.txt', content_type='text/plain')
            data.add_field('filename', 'test_document.txt')
            data.add_field('file_type', 'text')
            
            print("   Uploading file...")
            async with self.session.post(
                f"{API_BASE_URL}/api/knowledge/import/file",
                data=data
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    print("✅ File import successful")
                    
                    # Display results
                    print(f"   Import ID: {result.get('import_id', 'N/A')}")
                    print(f"   Status: {result.get('status', 'N/A')}")
                    print(f"   Filename: {result.get('filename', 'N/A')}")
                    
                    return result.get('import_id')
                    
                else:
                    error_text = await response.text()
                    print(f"❌ File import failed: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            print(f"❌ File import request failed: {e}")
            return None
        finally:
            # Clean up test file
            if test_file_path.exists():
                test_file_path.unlink()
    
    async def test_import_status(self, import_id):
        """Test checking import status"""
        if not import_id:
            return
            
        print(f"\n4. Testing Import Status Check (ID: {import_id})...")
        
        try:
            async with self.session.get(f"{API_BASE_URL}/api/knowledge/import/progress/{import_id}") as response:
                if response.status == 200:
                    status_data = await response.json()
                    print("✅ Status check successful")
                    print(f"   Status: {status_data.get('status', 'N/A')}")
                    
                    # Fix progress display - handle both percentage and ratio formats
                    progress = status_data.get('progress', 0)
                    if progress > 100:
                        # If progress is over 100, it's likely already a percentage that got multiplied
                        progress_display = f"{progress/100:.1f}%"
                    else:
                        # Normal percentage display
                        progress_display = f"{progress:.1f}%"
                    
                    print(f"   Progress: {progress_display}")
                    print(f"   Current Step: {status_data.get('current_step', 'N/A')}")
                    
                    if 'completed_steps' in status_data:
                        print(f"   Completed Steps: {len(status_data['completed_steps'])}/{status_data.get('total_steps', 0)}")
                        
                else:
                    error_text = await response.text()
                    print(f"❌ Status check failed: {response.status} - {error_text}")
                    
        except Exception as e:
            print(f"❌ Status check request failed: {e}")
    
    async def test_websocket_progress(self):
        """Test WebSocket progress notifications"""
        print("\n5. Testing WebSocket Progress Notifications...")
        
        try:
            import websockets
            
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                print("✅ WebSocket connected")
                
                # Send a test import in parallel
                asyncio.create_task(self.trigger_test_import_for_websocket())
                
                # Listen for progress messages for 10 seconds
                print("   Listening for progress messages (10 seconds)...")
                end_time = time.time() + 10
                message_count = 0
                
                while time.time() < end_time:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        
                        # Check for any knowledge-related progress messages
                        if (data.get('type') in ['knowledge_import_progress', 'knowledge_processing_started', 'knowledge_processing_progress', 'knowledge_processing_complete'] or
                            'knowledge' in data.get('type', '').lower() or
                            'import' in data.get('type', '').lower()):
                            message_count += 1
                            progress_data = data.get('data', data)  # Handle both nested and flat structures
                            step = progress_data.get('current_step', progress_data.get('step', 'unknown'))
                            progress = progress_data.get('progress', 0)
                            print(f"   📡 Progress: {step} - {progress:.1f}%")
                            
                    except asyncio.TimeoutError:
                        continue
                    except json.JSONDecodeError:
                        continue
                
                print(f"✅ Received {message_count} progress messages")
                
        except ImportError:
            print("❌ websockets package not available, skipping WebSocket test")
        except Exception as e:
            print(f"❌ WebSocket test failed: {e}")
    
    async def trigger_test_import_for_websocket(self):
        """Trigger a test import to generate WebSocket messages"""
        await asyncio.sleep(2)  # Wait a bit before starting
        
        test_data = {
            "content": "This is a test document for WebSocket progress monitoring. It contains some basic text about artificial intelligence and machine learning concepts.",
            "title": "WebSocket Test"
        }
        
        try:
            async with self.session.post(f"{API_BASE_URL}/api/knowledge/import/text", json=test_data) as response:
                pass  # Just trigger the import, don't wait for response
        except Exception:
            pass  # Ignore errors in this helper method

async def main():
    """Main test function"""
    
    print("Enhanced NLP Knowledge Pipeline API Tests")
    print("=" * 50)
    
    async with KnowledgeImportAPITester() as tester:
        # Test 1: Health check
        if not await tester.test_health_check():
            print("\n❌ API server is not available. Please start the server first:")
            print("   ./start-godelos.sh --dev")
            return 1
        
        # Test 2: Text import
        import_id = await tester.test_knowledge_import_text()
        
        # Test 3: File import
        file_import_id = await tester.test_knowledge_import_file()
        
        # Test 4: Status check
        await tester.test_import_status(import_id or file_import_id)
        
        # Test 5: WebSocket progress (optional)
        await tester.test_websocket_progress()
        
        print("\n" + "=" * 50)
        print("✅ API tests completed!")
        print("=" * 50)
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
