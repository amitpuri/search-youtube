# Search YouTube

A YouTube search application demonstrating three different implementation approaches for searching YouTube content.

## 🚀 Quick Start

1. **Get a YouTube API Key** from [Google Cloud Console](https://console.developers.google.com/)
2. **Choose your approach** (see options below)
3. **Clone and run**:

```bash
git clone <repository-url>
cd search-youtube
```

## 📁 Project Structure

| Component | Description | Port |
|-----------|-------------|------|
| `search-youtube/` | Direct Flask app using YouTube Data API | 5000 |
| `search-youtube-mcp-server/` | MCP server for structured search | 8000 |
| `search-youtube-via-mcp/` | Flask app that consumes MCP server | 5001 |

## 🛠️ Setup Options

### Option 1: Direct Flask App (Simplest)

```bash
cd search-youtube
pip install -r requirements.txt
cp env.example .env
# Add your API key to .env: YOUTUBE_API_KEY=your_key_here
python main.py
```

**Features:**
- Web interface + JSON API
- Search videos, channels, playlists
- Available at `http://localhost:5000`

### Option 2: MCP Server (Structured)

```bash
cd search-youtube-mcp-server
pip install -r requirements.txt
cp env.example .env
# Add your API key to .env: YOUTUBE_API_KEY=your_key_here
python youtube_mcp_server.py
```

**Features:**
- Model Context Protocol implementation
- Multiple search tools with detailed statistics
- Available at `http://localhost:8000`

### Option 3: Flask + MCP (Hybrid)

```bash
# Terminal 1: Start MCP server (Option 2)
# Terminal 2:
cd search-youtube-via-mcp
pip install -r requirements.txt
cp env.example .env
# Configure: MCP_SERVER_URL=http://localhost:8000
python main.py
```

**Features:**
- Web interface powered by MCP server
- Health checks and debug endpoints
- Available at `http://localhost:5001`

## 🔍 Usage Examples

### Web Interface
Visit the respective URLs to use the web interface:
- Direct Flask: `http://localhost:5000`
- MCP Client: `http://localhost:5001`

### API Endpoints

#### Direct Flask App
```bash
# Search videos
curl "http://localhost:5000/search?q=python%20tutorial&type=videos"

# Search all content types
curl "http://localhost:5000/search?q=python%20tutorial&type=all"
```

#### MCP Server
```bash
# Search using MCP protocol
curl -X POST "http://localhost:8000/mcp" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search_youtube_videos",
      "arguments": {
        "query": "python tutorial",
        "max_results": 10
      }
    }
  }'
```

### Python Integration

```python
import requests

# Direct Flask app
response = requests.get("http://localhost:5000/search", params={
    "q": "python tutorial",
    "type": "videos"
})
results = response.json()
print(f"Found {len(results['videos'])} videos")
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `YOUTUBE_API_KEY` | YouTube Data API key (required) | - |
| `FLASK_HOST` | Flask host binding | `0.0.0.0` |
| `FLASK_PORT` | Flask port | `5000` (direct), `5001` (MCP client) |
| `MCP_HOST` | MCP server host | `127.0.0.1` |
| `MCP_PORT` | MCP server port | `8000` |
| `MCP_SERVER_URL` | MCP server URL for client | `http://0.0.0.0:8000` |

### API Endpoints Summary

| Component | Endpoint | Description |
|-----------|----------|-------------|
| Direct Flask | `GET /search` | Search API |
| MCP Server | `POST /mcp` | MCP protocol endpoint |
| MCP Client | `GET /search` | Search via MCP |
| MCP Client | `GET /health` | Health check |
| MCP Client | `GET /debug` | Debug info |

## 🔧 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **API Key Error** | Enable YouTube Data API v3 in Google Cloud Console |
| **MCP Connection Failed** | Verify MCP server is running on port 8000 |
| **Port Conflicts** | Change ports in `.env` files (5000, 8000, 5001) |

### Debug Commands

```bash
# Check MCP server health
curl http://localhost:8000/mcp

# Check MCP client status  
curl http://localhost:5001/status

# Debug connectivity
curl http://localhost:5001/debug
```

## 🛠️ Development

### Project Structure
- `search-youtube/main.py` - Direct Flask implementation
- `search-youtube-mcp-server/youtube_mcp_server.py` - MCP server
- `search-youtube-via-mcp/main.py` - MCP client app

### Key Dependencies
- **Flask** - Web framework
- **fastmcp** - MCP protocol implementation  
- **google-api-python-client** - YouTube Data API client
- **python-dotenv** - Environment variable management

### Testing

#### Basic Component Testing
```bash
# Test each component
python search-youtube/main.py                    # Direct Flask
python search-youtube-mcp-server/youtube_mcp_server.py  # MCP Server
python search-youtube-via-mcp/main.py            # MCP Client
```

#### Testing with AI Clients

##### 1. Testing with Claude Code

**Setup:**
1. Install Claude Code in your IDE
2. Add the YouTube MCP server using the [official Claude Code MCP documentation](https://docs.anthropic.com/en/docs/claude-code/mcp)

**Configuration:**
Add the MCP server using Claude Code's command-line interface:

```bash
# Add the YouTube MCP server as an HTTP server
claude mcp add --transport http youtube-search http://127.0.0.1:8000/mcp
```

**Alternative: JSON Configuration**
Create a `.mcp.json` file in your project root:

```json
{
  "mcpServers": {
    "youtube-search": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

**Testing:**
1. Start the MCP server: `python youtube_mcp_server.py`
2. Open Claude Code in your IDE
3. Ask Claude to search YouTube: *"Find Python tutorial videos"*
4. Verify Claude uses the MCP tools to perform searches
5. Use `/mcp` command to manage MCP connections and authentication

##### 2. Testing with Gemini CLI

**Setup:**
```bash
# Install Gemini CLI
pip install google-generativeai

# Set up authentication
export GOOGLE_API_KEY="your_gemini_api_key"
```

**Configuration:**
Create a configuration file for MCP server connection following the [official Gemini CLI MCP documentation](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md):

```json
{
  "mcp_servers": {
    "youtube_search": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

**Testing:**
```bash
# Start MCP server
cd search-youtube-mcp-server
python youtube_mcp_server.py

# In another terminal, test with Gemini CLI
gemini-cli --mcp-config config.json "Search for cooking videos on YouTube"
```

**Alternative: Direct MCP Server Connection**
```bash
# Connect directly to running MCP server
gemini-cli --mcp-server "http://localhost:8000" "Find Python tutorial videos"
```

#### Manual Testing

**Test MCP Server Directly:**
```bash
# Test video search
curl -X POST "http://localhost:8000/mcp" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search_youtube_videos",
      "arguments": {
        "query": "python tutorial",
        "max_results": 5
      }
    }
  }'
```

## 📄 License

Open source - see license file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

**Need help?** Check the troubleshooting section or open an issue.
