
import http.server
import socketserver
import os
import webbrowser

PORT = 8000
DIRECTORY = "docs"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

def start_server():
    if not os.path.exists(DIRECTORY):
        print(f"❌ Error: {DIRECTORY} folder not found.")
        return

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"🚀 Dashboard Server started at http://localhost:{PORT}")
        print(f"📁 Serving files from: {os.path.abspath(DIRECTORY)}")
        print("Press Ctrl+C to stop the server.")
        
        # Open browser automatically
        webbrowser.open(f"http://localhost:{PORT}")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Server stopped.")

if __name__ == "__main__":
    start_server()
