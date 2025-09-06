# Game Benchmarking Automation - Deployment Guide

## Architecture Overview

```
Frontend (React) ↔ Main Backend Server ↔ Multiple SUTs
                                      ↕
                                 Omniparser Server
```

## Setup Instructions

### 1. Backend Server Setup

#### Prerequisites
- Python 3.8+
- Your existing modules directory
- Access to SUTs on the network

#### Installation
```bash
# Clone/copy your existing codebase
cd game-benchmark-automation

# Install backend dependencies
pip install -r requirements_backend.txt

# Create necessary directories
mkdir -p logs
mkdir -p config/games

# Copy your existing YAML configs to config/games/
cp your_existing_configs/*.yaml config/games/

# Set environment variables (optional)
export FLASK_ENV=production
export BACKEND_HOST=0.0.0.0
export BACKEND_PORT=5000
```

#### Running the Backend Server
```bash
# Development mode
python backend_server.py --debug

# Production mode
python backend_server.py --host 0.0.0.0 --port 5000

# With custom omniparser URL
OMNIPARSER_URL=http://your-omniparser-server:8000 python backend_server.py
```

### 2. Frontend Setup

#### Prerequisites
- Node.js 18+
- npm or yarn

#### Installation
```bash
# Create frontend directory
mkdir frontend
cd frontend

# Initialize project with package.json
npm init -y
# Copy the package.json content from the artifact

# Install dependencies
npm install

# Create src directory structure
mkdir -p src/{components,pages,contexts,utils}

# Copy all the frontend code from artifacts
# - src/App.tsx
# - src/contexts/SocketContext.tsx
# - src/pages/Dashboard.tsx
# - src/components/... (all component files)
# - src/utils/api.ts
# - vite.config.ts
# - tailwind.config.js
# - tsconfig.json
```

#### Environment Configuration
Create `.env` file:
```bash
# .env
VITE_BACKEND_URL=http://localhost:5000
```

#### Running the Frontend
```bash
# Development mode
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### 3. SUT Service (No Changes Required)

Your existing `gemma_sut_service.py` remains unchanged. Just ensure it's running on all your test machines:

```bash
# On each SUT machine
python gemma_sut_service.py --host 0.0.0.0 --port 8080
```

### 4. Omniparser Server (No Changes Required)

Keep your existing omniparser server running as usual:
```bash
# Your existing omniparser setup
python omniparser_server.py --port 8000
```

## Configuration

### Backend Configuration

The backend automatically discovers SUTs and loads game configurations. You can customize:

#### SUT Discovery
Edit `backend_server.py`, find the `sut_discovery_loop` method and modify the `sut_candidates` list:
```python
sut_candidates = [
    "192.168.50.230",
    "192.168.50.231", 
    "192.168.1.100",
    "192.168.1.101",
    # Add your SUT IPs here
]
```

#### Game Configuration Directory
By default, the backend looks for YAML files in `config/games/`. You can change this in the backend constructor:
```python
self.config_dir = "config/games"  # Change this path if needed
```

### Frontend Configuration

#### Backend URL
Set the backend URL in your `.env` file:
```bash
VITE_BACKEND_URL=http://your-backend-server:5000
```

#### Proxy Configuration (Development)
The Vite config includes proxy settings for development. Modify `vite.config.ts` if needed:
```typescript
proxy: {
  '/api': {
    target: 'http://your-backend:5000',
    changeOrigin: true,
  },
}
```

## Production Deployment

### Backend Deployment Options

#### Option 1: Simple Python Server
```bash
# Use gunicorn for production
pip install gunicorn
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 backend_server:app
```

#### Option 2: Docker Deployment
Create `Dockerfile` for backend:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements_backend.txt .
RUN pip install -r requirements_backend.txt

COPY . .
EXPOSE 5000

CMD ["python", "backend_server.py", "--host", "0.0.0.0", "--port", "5000"]
```

#### Option 3: Systemd Service
Create `/etc/systemd/system/game-benchmark.service`:
```ini
[Unit]
Description=Game Benchmark Backend
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/your/app
ExecStart=/path/to/python backend_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Frontend Deployment Options

#### Option 1: Static Hosting (Nginx, Apache, etc.)
```bash
# Build the frontend
npm run build

# Copy dist/ directory to your web server
cp -r dist/* /var/www/html/
```

#### Option 2: Node.js Server
```bash
# Build first
npm run build

# Serve with a simple server
npm install -g serve
serve -s dist -l 3000
```

#### Option 3: Docker
```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
```

## Network Configuration

### Firewall Rules
Ensure these ports are accessible:
- **Backend Server**: Port 5000 (or your chosen port)
- **Frontend**: Port 3000 (development) or 80/443 (production)
- **SUTs**: Port 8080 (for each SUT)
- **Omniparser**: Port 8000

### CORS Configuration
The backend includes CORS headers for cross-origin requests. If you need to restrict origins:
```python
CORS(self.app, origins=["http://your-frontend-domain.com"])
```

## Monitoring and Logs

### Backend Logs
- Main log: `backend_server.log`
- Run-specific logs: `logs/{game_name}/run_{timestamp}/automation.log`

### Health Checks
- Backend health: `GET /api/status`
- SUT health: Automatic discovery every 10 seconds
- Omniparser health: `GET /api/omniparser/status`

## Troubleshooting

### Common Issues

#### Backend can't discover SUTs
1. Check network connectivity: `ping {SUT_IP}`
2. Verify SUT service is running: `curl http://{SUT_IP}:8080/status`
3. Check firewall rules on both backend and SUT

#### Frontend can't connect to backend
1. Check backend is running: `curl http://{BACKEND_IP}:5000/api/status`
2. Verify CORS settings
3. Check network connectivity

#### WebSocket connection fails
1. Ensure both HTTP and WebSocket traffic is allowed
2. Check proxy settings if behind a reverse proxy
3. Verify SocketIO is working: Check browser network tab

#### Game configurations not loading
1. Check `config/games/` directory exists and contains YAML files
2. Verify YAML syntax: `python -c "import yaml; yaml.safe_load(open('config.yaml'))"`
3. Check backend logs for parsing errors

### Debug Mode
Enable debug logging:
```python
# In backend_server.py
logging.basicConfig(level=logging.DEBUG)
```

## Advanced Features

### Adding New Game Configurations
1. Create YAML file in `config/games/`
2. Use existing format (steps or state machine)
3. Backend automatically reloads configurations
4. Or use the API: `POST /api/games/reload`

### Custom SUT Discovery
Modify the `sut_discovery_loop` method to implement:
- Network scanning
- mDNS/Bonjour discovery
- Database-based SUT registry

### Extending the API
Add new endpoints to `backend_server.py`:
```python
@self.app.route('/api/custom-endpoint', methods=['GET'])
def custom_endpoint():
    return jsonify({'status': 'success'})
```

### Real-time Notifications
The WebSocket implementation supports:
- SUT status changes
- Run progress updates
- Game configuration reloads
- Custom events

### Performance Optimization
- Use Redis for session storage in multi-instance deployments
- Implement request rate limiting
- Add caching for game configurations
- Use database for run history storage

## Migration from GUI Application

### Data Migration
Your existing logs and configurations should work as-is:
1. Copy YAML configs to `config/games/`
2. Existing log structure is preserved
3. No changes needed to SUT service

### Feature Parity
The web interface provides all GUI functionality:
- [OK] SUT connection management
- [OK] Game configuration selection
- [OK] Vision model selection (configured in backend)
- [OK] Real-time progress monitoring
- [OK] Run history and results
- [OK] Screenshot and log access

### Additional Web Benefits
- Multi-user access
- Remote operation
- Mobile device support
- Better scalability
- RESTful API for integration