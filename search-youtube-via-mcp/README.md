# YouTube Search via MCP

A Flask web application that demonstrates how to use the YouTube Search MCP Server. This application provides a web interface for searching YouTube content using the Model Context Protocol (MCP) server.

## Features

- **Web Interface**: User-friendly search interface for YouTube content
- **MCP Integration**: Uses the YouTube Search MCP Server for all search functionality
- **Multiple Content Types**: Search for videos, channels, playlists, or all content types
- **REST API**: JSON endpoints for programmatic access
- **Health Monitoring**: Built-in health checks for MCP server connectivity

## Prerequisites

1. **YouTube Search MCP Server**: Must be running on `0.0.0.0:8000`
2. **Python 3.8+**: For running the Flask application
3. **YouTube API Key**: Configured in the MCP server

## Setup

### 1. Install Dependencies

```bash
# Activate your virtual environment
cd search-via-mcp
source youtube-search-via-mcp-env/Scripts/activate  # Windows
# or
source youtube-search-via-mcp-env/bin/activate      # Linux/Mac

# Install requirements
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the environment file and configure the MCP server URL:

```bash
cp env.example .env
```

Edit `.env` and configure:

```env
# MCP Server Configuration
MCP_SERVER_URL=http://localhost:8080

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
FLASK_HOST=0.0.0.0
FLASK_PORT=5001
```

**Note**: The MCP server must be running on `localhost:8080` for this application to work. The server binds to `0.0.0.0:8080` to accept connections from any interface, but clients connect to `localhost:8080`.

### 3. Start the MCP Server

In another terminal, start the YouTube MCP Server:

```bash
cd mcp-server
python youtube_mcp_server.py --mode http --host 0.0.0.0 --port 8000
```

### 4. Start the Flask Application

```bash
python main.py
```

You should see:
```
Starting YouTube Search via MCP on 0.0.0.0:5001
MCP Server URL: http://0.0.0.0:8000
Available endpoints:
- GET /: Main search page
- GET /search?q=query&type=all|videos|channels|playlists: API endpoint
- GET /health: Health check
```

## Usage

### Web Interface

1. Open your browser and go to `http://localhost:5001`
2. Enter a search query (defaults to "Model Context Protocol")
3. View results for videos, channels, and playlists

### API Endpoints

#### Main Search Page
- **GET /** - Main search interface with form and results

#### Search API
- **GET /search?q=query&type=all** - Search all content types
- **GET /search?q=query&type=videos** - Search videos only
- **GET /search?q=query&type=channels** - Search channels only
- **GET /search?q=query&type=playlists** - Search playlists only

#### Health Check
- **GET /health** - Check MCP server connectivity and available tools

### Example API Calls

```bash
# Search for all content types
curl "http://localhost:5001/search?q=Python+tutorials&type=all"

# Search for videos only
curl "http://localhost:5001/search?q=machine+learning&type=videos"

# Health check
curl "http://localhost:5001/health"
```

## Architecture

This application demonstrates a clean separation of concerns:

- **Flask Web App**: Handles HTTP requests, user interface, and response formatting
- **MCP Server**: Provides YouTube search functionality via the Model Context Protocol
- **HTTP Communication**: RESTful API calls between the web app and MCP server

## MCP Server Integration

The application communicates with the MCP server using the Model Context Protocol:

- **Tool Discovery**: POST requests to `/mcp` with `tools/list` method
- **Tool Execution**: POST requests to `/mcp` with `tools/call` method
- **Response Format**: JSON-RPC 2.0 compliant responses
- **Error Handling**: Graceful fallbacks when the MCP server is unavailable

### MCP Protocol Details

The application uses the standard MCP protocol:

#### Tool Discovery
```json
POST /mcp
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

#### Tool Execution
```json
POST /mcp
{
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
}
```

### Available MCP Tools

- `search_youtube_videos` - Search for YouTube videos
- `search_youtube_channels` - Search for YouTube channels
- `search_youtube_playlists` - Search for YouTube playlists
- `search_youtube_all` - Comprehensive search across all content types

## Configuration

### Environment Variables

- `MCP_SERVER_URL`: URL of the MCP server (default: http://localhost:8080)
- `FLASK_HOST`: Flask server host (default: 0.0.0.0)
- `FLASK_PORT`: Flask server port (default: 5001)
- `FLASK_DEBUG`: Debug mode (default: True)

### Network Configuration

- **MCP Server**: Must be accessible on `localhost:8080` (server binds to `0.0.0.0:8080`)
- **Flask App**: Runs on `0.0.0.0:5001` by default
- **Cross-Network Access**: Both servers bind to all interfaces for network access

## Troubleshooting

### MCP Server Connection Issues

1. **Check MCP Server Status**:
   ```bash
   # Test tools list
   curl -X POST "http://localhost:8080/mcp" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   ```

2. **Verify Network Access**:
   - Ensure MCP server is running on `localhost:8080`
   - Check firewall settings
   - Verify network connectivity

3. **Check Health Endpoint**:
   ```bash
   curl "http://localhost:5001/health"
   ```

### Common Issues

- **Connection Refused**: MCP server not running or wrong port
- **Timeout Errors**: Network latency or MCP server overload
- **Parse Errors**: MCP server response format changes

## Development

### Adding New Features

1. **New MCP Tools**: Add parsing logic in the `parse_mcp_response` function
2. **API Endpoints**: Add new routes in the Flask application
3. **UI Enhancements**: Modify the HTML templates

### Testing

```bash
# Test MCP server connectivity
curl -X POST "http://localhost:8080/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Test Flask application
curl "http://localhost:5001/health"

# Test search functionality
curl "http://localhost:5001/search?q=test&type=all"

# Run MCP protocol tests
python test_mcp.py
```

## Security Considerations

- **Network Access**: Both servers bind to `0.0.0.0` for network accessibility
- **API Rate Limiting**: Consider implementing rate limiting for production use
- **Input Validation**: Search queries are passed directly to the MCP server
- **Error Handling**: Sensitive information is not exposed in error messages

## Production Deployment

For production use:

1. **Set `FLASK_DEBUG=False`** in environment variables
2. **Use a production WSGI server** like Gunicorn or uWSGI
3. **Implement proper logging** and monitoring
4. **Add authentication** if needed
5. **Use HTTPS** for secure communication
6. **Implement rate limiting** and request validation
