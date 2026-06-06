# NeoTrade3 Dashboard - Deployment Guide

## Flask + Cpolar Integration

### 1. Build the Dashboard

```bash
cd neotrade3-dashboard
npm install
npm run build
```

The built files will be in the `dist/` directory.

### 2. Flask Integration

Copy the `dist/` folder contents to your Flask static folder:

```python
# Flask app structure
app/
├── static/
│   ├── index.html          # Copy from dist/
│   ├── assets/             # Copy from dist/assets/
│   └── ...
├── templates/
└── app.py
```

### 3. Flask Routes

```python
from flask import Flask, send_from_directory, jsonify
import os

app = Flask(__name__, static_folder='static')

# Serve the dashboard
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# Serve static assets
@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(os.path.join('static', path)):
        return send_from_directory('static', path)
    return send_from_directory('static', 'index.html')

# API proxy to NeoTrade3 API
@app.route('/api/<path:path>')
def proxy_api(path):
    import requests
    api_url = f'http://127.0.0.1:18030/api/{path}'
    response = requests.get(api_url, params=request.args)
    return jsonify(response.json()), response.status_code
```

### 4. Cpolar Configuration

```bash
# Install cpolar
curl -L https://www.cpolar.com/static/downloads/install-release-cpolar.sh | sudo bash

# Authenticate
cpolar authtoken <your_token>

# Create tunnel
cpolar http 5000
```

### 5. Environment Variables

Create a `.env` file in your Flask app:

```
NEOTRADE3_API_URL=http://127.0.0.1:18030
FLASK_ENV=production
FLASK_PORT=5000
```

### 6. Production Build Notes

- The dashboard is built as a Single Page Application (SPA)
- All routes are handled by React Router
- Flask must serve `index.html` for all non-API routes
- API calls are proxied to the NeoTrade3 API server

### 7. API Configuration

The dashboard expects the API at `/api` path. In production, you can configure this via environment variable:

```javascript
// In src/services/api.js
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
```

Build with custom API URL:
```bash
VITE_API_BASE_URL=https://your-api-domain.com npm run build
```

### 8. Security Considerations

- Set `FLASK_ENV=production` for production
- Use HTTPS via Cpolar or reverse proxy
- Implement API key authentication for POST endpoints
- Add CORS headers in Flask if needed

### 9. Troubleshooting

**Blank page after deployment:**
- Check browser console for 404 errors
- Ensure Flask is serving static files correctly
- Verify `index.html` is served for all routes

**API connection errors:**
- Verify NeoTrade3 API is running on port 18030
- Check Flask proxy routes are configured
- Test API directly: `curl http://127.0.0.1:18030/healthz`

**CORS errors:**
- Add CORS headers in Flask
- Or ensure API and dashboard are on same origin
