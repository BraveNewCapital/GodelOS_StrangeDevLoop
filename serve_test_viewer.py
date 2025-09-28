#!/usr/bin/env python3
"""
Simple HTTP server to serve the test results viewer
"""
import http.server
import socketserver
import webbrowser
import os
from pathlib import Path

def serve_viewer():
    """Start a simple HTTP server to serve the test results viewer"""
    PORT = 8080
    
    # Change to the directory containing the HTML file
    viewer_path = Path("test_results_viewer.html")
    if not viewer_path.exists():
        print("❌ test_results_viewer.html not found!")
        return
    
    # Start simple HTTP server
    Handler = http.server.SimpleHTTPRequestHandler
    
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"🌐 Serving test results viewer at http://localhost:{PORT}")
            print(f"📁 Files available:")
            print(f"  • Viewer: http://localhost:{PORT}/test_results_viewer.html")
            
            # Check for results files
            results_files = list(Path(".").glob("*test_results.json"))
            for result_file in results_files:
                print(f"  • Results: http://localhost:{PORT}/{result_file.name}")
            
            print(f"\n💡 Instructions:")
            print(f"  1. Open http://localhost:{PORT}/test_results_viewer.html")
            print(f"  2. Upload any *test_results.json file (a bundled sample loads automatically if present)")
            print(f"  3. Use Ctrl+C to stop the server")
            
            # Try to open browser automatically
            try:
                webbrowser.open(f"http://localhost:{PORT}/test_results_viewer.html")
                print(f"🚀 Opening browser...")
            except:
                pass
                
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print(f"\n👋 Server stopped")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {PORT} is already in use. Try a different port or stop existing server.")
        else:
            print(f"❌ Error starting server: {e}")

if __name__ == "__main__":
    print("🧠 GödelOS Test Results Viewer Server")
    print("=" * 40)
    serve_viewer()