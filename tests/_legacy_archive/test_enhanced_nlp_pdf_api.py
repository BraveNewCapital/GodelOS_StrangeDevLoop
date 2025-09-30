#!/usr/bin/env python3
"""
API test for the Enhanced NLP Knowledge Pipeline with Real PDF
Tests the knowledge import endpoints with actual PDF documents
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
    """Test the knowledge import API endpoints with real documents"""
    
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
    
    async def test_knowledge_import_pdf(self):
        """Test PDF-based knowledge import with real PDF"""
        print("\n3. Testing PDF Knowledge Import with Real Document...")
        
        # Check for available PDF files
        pdf_candidates = [
            "godelos_arxiv_paper_v2.pdf",
            "test_ai_comprehensive.txt"  # Fallback to text file
        ]
        
        pdf_file_path = None
        for candidate in pdf_candidates:
            path = Path(candidate)
            if path.exists():
                pdf_file_path = path
                break
        
        if not pdf_file_path:
            print("❌ No suitable test file found")
            return None
        
        file_size = pdf_file_path.stat().st_size
        print(f"   Using file: {pdf_file_path.name} ({file_size / 1024:.1f} KB)")
        
        # Determine file type
        if pdf_file_path.suffix.lower() == '.pdf':
            content_type = 'application/pdf'
            file_type = 'pdf'
        else:
            content_type = 'text/plain'
            file_type = 'text'
        
        try:
            # Prepare multipart form data
            data = aiohttp.FormData()
            data.add_field('file', open(pdf_file_path, 'rb'), 
                          filename=pdf_file_path.name, 
                          content_type=content_type)
            data.add_field('filename', pdf_file_path.name)
            data.add_field('file_type', file_type)
            
            print(f"   Uploading {file_type.upper()} file...")
            start_time = time.time()
            
            async with self.session.post(
                f"{API_BASE_URL}/api/knowledge/import/file",
                data=data
            ) as response:
                
                upload_time = time.time() - start_time
                print(f"   Upload completed in {upload_time:.2f} seconds")
                
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
            # Make sure file is closed
            try:
                data._fields[0][1].close()
            except:
                pass
    
    async def test_import_status(self, import_id):
        """Test checking import status with improved progress display"""
        if not import_id:
            return
            
        print(f"\n4. Testing Import Status Check (ID: {import_id})...")
        
        # Check status multiple times to see progress
        for i in range(3):
            try:
                async with self.session.get(f"{API_BASE_URL}/api/knowledge/import/progress/{import_id}") as response:
                    if response.status == 200:
                        status_data = await response.json()
                        print(f"✅ Status check {i+1} successful")
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
                        
                        # Break if completed
                        if status_data.get('status') in ['completed', 'failed']:
                            break
                            
                    else:
                        error_text = await response.text()
                        print(f"❌ Status check failed: {response.status} - {error_text}")
                        break
                        
            except Exception as e:
                print(f"❌ Status check request failed: {e}")
                break
            
            # Wait before next check
            if i < 2:
                await asyncio.sleep(2)
    
    async def test_websocket_progress(self):
        """Test WebSocket progress notifications"""
        print("\n5. Testing WebSocket Progress Notifications...")
        
        try:
            import websockets
            
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                print("✅ WebSocket connected")
                
                # Send a test import in parallel
                asyncio.create_task(self.trigger_test_import_for_websocket())
                
                # Listen for progress messages for 15 seconds
                print("   Listening for progress messages (15 seconds)...")
                end_time = time.time() + 15
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
            "content": "This is a test document for WebSocket progress monitoring with enhanced NLP processing. It contains information about artificial intelligence, machine learning, and natural language processing concepts that should trigger various processing steps.",
            "title": "WebSocket Test Document"
        }
        
        try:
            async with self.session.post(f"{API_BASE_URL}/api/knowledge/import/text", json=test_data) as response:
                pass  # Just trigger the import, don't wait for response
        except Exception:
            pass  # Ignore errors in this helper method

async def main():
    """Main test function"""
    
    print("Enhanced NLP Knowledge Pipeline API Tests with Real PDF")
    print("=" * 60)
    
    async with KnowledgeImportAPITester() as tester:
        # Test 1: Health check
        if not await tester.test_health_check():
            print("\n❌ API server is not available. Please start the server first:")
            print("   ./start-godelos.sh --dev")
            return 1
        
        # Test 2: Text import
        import_id = await tester.test_knowledge_import_text()
        
        # Test 3: PDF/File import with real document
        pdf_import_id = await tester.test_knowledge_import_pdf()
        
        # Test 4: Status check (use PDF import ID if available, otherwise text import ID)
        test_import_id = pdf_import_id or import_id
        await tester.test_import_status(test_import_id)
        
        # Test 5: WebSocket progress (optional)
        await tester.test_websocket_progress()
        
        print("\n" + "=" * 60)
        print("✅ API tests completed!")
        print("=" * 60)
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
