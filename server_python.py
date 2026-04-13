"""
Simple HTTP server to serve the web interface
Run this instead of Node.js server if you don't have Node installed
"""
import http.server
import socketserver
import json
import os
from urllib.parse import urlparse, parse_qs
import subprocess
from pathlib import Path

PORT = 3000

class EmailCampaignHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="public", **kwargs)
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        # API Routes
        if parsed_path.path.startswith('/api/'):
            self.handle_api_get(parsed_path.path)
        else:
            # Serve static files
            super().do_GET()
    
    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path.startswith('/api/'):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except:
                data = {}
            self.handle_api_post(parsed_path.path, data)
    
    def do_PUT(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path.startswith('/api/'):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except:
                data = {}
            self.handle_api_put(parsed_path.path, data)
    
    def do_DELETE(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path.startswith('/api/'):
            self.handle_api_delete(parsed_path.path)
    
    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def handle_api_get(self, path):
        try:
            if path == '/api/stats':
                tracking = self.load_json('email_tracking.json') or {'sent_emails': [], 'processed_companies': []}
                generated = self.load_json('generated_emails.json') or []
                startups = self.load_json('startups.json') or {'data': []}
                
                stats = {
                    'totalStartups': len(startups.get('data', [])),
                    'emailsGenerated': len(generated),
                    'emailsSent': len(tracking.get('sent_emails', [])),
                    'emailsPending': len(generated) - len(tracking.get('sent_emails', [])),
                    'processedCompanies': len(tracking.get('processed_companies', []))
                }
                self.send_json_response(stats)
            
            elif path == '/api/resume':
                resume = self.load_json('resume.json')
                if resume:
                    self.send_json_response(resume)
                else:
                    self.send_json_response({'error': 'Resume not found'}, 404)
            
            elif path == '/api/startups':
                startups = self.load_json('startups.json') or {'data': []}
                self.send_json_response(startups)
            
            elif path == '/api/emails':
                emails = self.load_json('generated_emails.json') or []
                self.send_json_response(emails)
            
            elif path == '/api/tracking':
                tracking = self.load_json('email_tracking.json') or {'sent_emails': [], 'processed_companies': []}
                self.send_json_response(tracking)
            
            elif path == '/api/config':
                config = self.load_json('config.json') or {}
                # Load from .env if config.json doesn't exist
                if not config:
                    config = {
                        'gemini_api_key': os.getenv('GOOGLE_API_KEY', ''),
                        'gemini_model': os.getenv('GEMINI_MODEL', 'gemini-pro'),
                        'gmail_user': os.getenv('GMAIL_USER', ''),
                        'gmail_app_password': os.getenv('GMAIL_APP_PASSWORD', ''),
                        'resume_link': os.getenv('RESUME_LINK', ''),
                        'email_prompt': ''
                    }
                self.send_json_response(config)
                if resume:
                    self.send_json_response(resume)
                else:
                    self.send_json_response({'error': 'Resume not found'}, 404)
            
            elif path == '/api/startups':
                startups = self.load_json('startups.json') or {'data': []}
                self.send_json_response(startups)
            
            elif path == '/api/emails':
                emails = self.load_json('generated_emails.json') or []
                self.send_json_response(emails)
            
            elif path == '/api/tracking':
                tracking = self.load_json('email_tracking.json') or {'sent_emails': [], 'processed_companies': []}
                self.send_json_response(tracking)
            
            else:
                self.send_json_response({'error': 'Not found'}, 404)
        
        except Exception as e:
            self.send_json_response({'error': str(e)}, 500)
    
    def handle_api_post(self, path, data):
        try:
            if path == '/api/startups':
                startups = self.load_json('startups.json') or {'data': []}
                new_startup = {
                    'id': max([s.get('id', 0) for s in startups['data']], default=0) + 1,
                    **data
                }
                startups['data'].append(new_startup)
                self.save_json('startups.json', startups)
                self.send_json_response({'message': 'Startup added', 'data': new_startup})
            
            elif path == '/api/config':
                # Save configuration
                existing_config = self.load_json('config.json') or {}
                existing_config.update(data)
                self.save_json('config.json', existing_config)
                
                # Also update .env file
                self.update_env_file(data)
                
                self.send_json_response({'message': 'Configuration saved', 'data': existing_config})
            
            elif path == '/api/test-gmail':
                # Test Gmail connection
                import smtplib
                import ssl
                
                try:
                    context = ssl.create_default_context()
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                        server.login(data.get('gmail_user'), data.get('gmail_app_password'))
                    self.send_json_response({'success': True, 'message': 'Connection successful'})
                except Exception as e:
                    self.send_json_response({'success': False, 'error': str(e)})
            
            elif path == '/api/generate-emails':
                # Run Python script
                result = subprocess.run(['python', 'generate_emails.py'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    emails = self.load_json('generated_emails.json') or []
                    self.send_json_response({
                        'message': 'Emails generated successfully',
                        'count': len(emails),
                        'emails': emails
                    })
                else:
                    self.send_json_response({'error': 'Generation failed', 'details': result.stderr}, 500)
            
            elif path == '/api/send-emails':
                # Run Python script
                result = subprocess.run(['python', 'send_emails.py'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    self.send_json_response({
                        'message': 'Emails sent successfully',
                        'output': result.stdout
                    })
                else:
                    self.send_json_response({'error': 'Sending failed', 'details': result.stderr}, 500)
            
            else:
                self.send_json_response({'error': 'Not found'}, 404)
        
        except Exception as e:
            self.send_json_response({'error': str(e)}, 500)
    
    def handle_api_put(self, path, data):
        try:
            if path == '/api/resume':
                self.save_json('resume.json', data)
                self.send_json_response({'message': 'Resume updated', 'data': data})
            
            elif path.startswith('/api/startups/'):
                startup_id = int(path.split('/')[-1])
                startups = self.load_json('startups.json')
                for i, s in enumerate(startups['data']):
                    if s.get('id') == startup_id:
                        startups['data'][i] = {**startups['data'][i], **data}
                        self.save_json('startups.json', startups)
                        self.send_json_response({'message': 'Startup updated', 'data': startups['data'][i]})
                        return
                self.send_json_response({'error': 'Startup not found'}, 404)
            
            elif path.startswith('/api/emails/'):
                index = int(path.split('/')[-1])
                emails = self.load_json('generated_emails.json') or []
                if 0 <= index < len(emails):
                    emails[index] = {**emails[index], **data}
                    self.save_json('generated_emails.json', emails)
                    self.send_json_response({'message': 'Email updated', 'data': emails[index]})
                else:
                    self.send_json_response({'error': 'Email not found'}, 404)
            
            else:
                self.send_json_response({'error': 'Not found'}, 404)
        
        except Exception as e:
            self.send_json_response({'error': str(e)}, 500)
    
    def handle_api_delete(self, path):
        try:
            if path.startswith('/api/startups/'):
                startup_id = int(path.split('/')[-1])
                startups = self.load_json('startups.json')
                startups['data'] = [s for s in startups['data'] if s.get('id') != startup_id]
                self.save_json('startups.json', startups)
                self.send_json_response({'message': 'Startup deleted'})
            else:
                self.send_json_response({'error': 'Not found'}, 404)
        
        except Exception as e:
            self.send_json_response({'error': str(e)}, 500)
    
    def load_json(self, filename):
        try:
            filepath = Path(__file__).parent / filename
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    
    def save_json(self, filename, data):
        filepath = Path(__file__).parent / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def update_env_file(self, data):
        """Update .env file with new configuration"""
        try:
            env_path = Path(__file__).parent / '.env'
            
            # Read existing .env
            env_vars = {}
            if env_path.exists():
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
            
            # Update with new data
            if 'gemini_api_key' in data:
                env_vars['GOOGLE_API_KEY'] = data['gemini_api_key']
            if 'gemini_model' in data:
                env_vars['GEMINI_MODEL'] = data['gemini_model']
            if 'gmail_user' in data:
                env_vars['GMAIL_USER'] = data['gmail_user']
            if 'gmail_app_password' in data:
                env_vars['GMAIL_APP_PASSWORD'] = data['gmail_app_password']
            if 'resume_link' in data:
                env_vars['RESUME_LINK'] = data['resume_link']
            
            # Write back to .env
            with open(env_path, 'w') as f:
                for key, value in env_vars.items():
                    f.write(f'{key}={value}\n')
        
        except Exception as e:
            print(f"Error updating .env: {e}")
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

def run_server():
    with socketserver.TCPServer(("", PORT), EmailCampaignHandler) as httpd:
        print(f"╔════════════════════════════════════════════════════════════╗")
        print(f"║  🚀 Email Campaign Manager Server                          ║")
        print(f"╠════════════════════════════════════════════════════════════╣")
        print(f"║  Server running on: http://localhost:{PORT}               ║")
        print(f"║  Open this URL in your browser to access the interface    ║")
        print(f"║                                                            ║")
        print(f"║  Press Ctrl+C to stop the server                          ║")
        print(f"╚════════════════════════════════════════════════════════════╝")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
