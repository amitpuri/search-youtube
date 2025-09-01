import os
import json
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import time
import threading

# Load environment variables
load_dotenv()

app = Flask(__name__)

# MCP Server configuration
MCP_SERVER_URL = os.getenv('MCP_SERVER_URL', 'http://localhost:8080')
PROTOCOL_VERSION = os.getenv('MCP_PROTOCOL_VERSION', '2024-11-05')

_session_lock = threading.Lock()
_cached_session_id = None

def parse_sse_response(response_text):
    """
    Parse Server-Sent Events (SSE) response format.
    
    Args:
        response_text: Raw SSE response text
    
    Returns:
        Parsed JSON data or None if parsing fails
    """
    lines = response_text.strip().split('\n')
    data_content = None
    
    for line in lines:
        line = line.strip()
        if line.startswith('data: '):
            data_content = line[6:]  # Remove 'data: ' prefix
            break
    
    if data_content:
        try:
            return json.loads(data_content)
        except json.JSONDecodeError:
            return None
    
    return None

def get_or_create_session_id() -> str | None:
    global _cached_session_id
    with _session_lock:
        if _cached_session_id:
            return _cached_session_id
        
        # Complete MCP initialization sequence
        url = f"{MCP_SERVER_URL}/mcp"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        
        try:
            # Step 1: Initialize
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "clientInfo": {"name": "search-via-mcp", "version": "0.1.0"},
                    "capabilities": {},
                },
            }
            
            print(f"DEBUG: Sending initialize request: {json.dumps(init_payload, indent=2)}")
            init_resp = requests.post(url, json=init_payload, headers=headers, timeout=5)
            
            # Check if we got a session ID
            sid = init_resp.headers.get("mcp-session-id")
            if not sid or init_resp.status_code != 200:
                print(f"DEBUG: Initialize failed - Status: {init_resp.status_code}, Session ID: {sid}")
                print(f"DEBUG: Initialize response: {init_resp.text[:500]}")
                return None
            
            # Parse initialization response
            try:
                init_response = init_resp.json()
            except json.JSONDecodeError:
                init_response = parse_sse_response(init_resp.text)
            
            if not init_response or "error" in init_response:
                print(f"DEBUG: Initialize response error: {init_response}")
                return None
            
            print(f"DEBUG: Initialize successful, Session ID: {sid}")
            
            # Step 2: Send initialized notification (required by MCP protocol)
            headers["mcp-session-id"] = sid
            initialized_payload = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
            
            print(f"DEBUG: Sending initialized notification: {json.dumps(initialized_payload, indent=2)}")
            notif_resp = requests.post(url, json=initialized_payload, headers=headers, timeout=5)
            
            # Notifications may return 200, 204, or other success codes
            if 200 <= notif_resp.status_code <= 299:
                _cached_session_id = sid
                # Give server a brief moment to finish initialization
                time.sleep(0.25)
                print(f"DEBUG: MCP initialization sequence completed successfully")
                print(f"DEBUG: Notification response status: {notif_resp.status_code}")
                return sid
            else:
                print(f"DEBUG: Initialized notification failed - Status: {notif_resp.status_code}")
                print(f"DEBUG: Notification response: {notif_resp.text[:500]}")
                # Some servers might not handle notifications properly, so let's try anyway
                print(f"DEBUG: Proceeding anyway as some servers ignore notifications...")
                _cached_session_id = sid
                time.sleep(0.25)
                return sid
                
        except Exception as e:
            print(f"DEBUG: MCP initialization failed with exception: {e}")
            return None

def call_mcp_tool(tool_name, parameters, max_retries=3):
    """
    Call a tool on the MCP server via HTTP using the MCP protocol.
    
    Args:
        tool_name: Name of the tool to call
        parameters: Dictionary of parameters to pass to the tool
        max_retries: Maximum number of retries for server initialization
    
    Returns:
        Response from the MCP server
    """
    last_error = None
    
    for retry in range(max_retries):
        try:
            # The MCP server uses the /mcp endpoint for tool calls
            url = f"{MCP_SERVER_URL}/mcp"
            
            # Create the MCP tool call request
            session_id = get_or_create_session_id()
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "mcp-protocol-version": PROTOCOL_VERSION,
            }
            if session_id:
                headers["mcp-session-id"] = session_id
            
            # Standard MCP protocol format
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": parameters
                }
            }
            
            # Debug: Log the request being sent
            print(f"DEBUG: Sending MCP request: {json.dumps(mcp_request, indent=2)}")
            
            response = requests.post(url, json=mcp_request, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Check if response is empty or not JSON
            if not response.text.strip():
                if retry < max_retries - 1:
                    print(f"DEBUG: Empty response on retry {retry + 1}, waiting and retrying...")
                    time.sleep(0.5 * (retry + 1))  # Exponential backoff
                    continue
                else:
                    return {"error": "MCP Server returned empty response (server may still be initializing)"}
            
            # Parse the MCP response - try SSE format first, then regular JSON
            try:
                # First try to parse as regular JSON
                mcp_response = response.json()
            except json.JSONDecodeError:
                # If regular JSON fails, try SSE format
                mcp_response = parse_sse_response(response.text)
                if mcp_response is None:
                    # Log the raw response for debugging
                    raw_response = response.text[:500] if response.text else "Empty response"
                    print(f"DEBUG: Failed to parse JSON and SSE on retry {retry + 1}. Raw response: {raw_response}...")
                    
                    if retry < max_retries - 1:
                        print(f"DEBUG: Retrying in {0.5 * (retry + 1)} seconds...")
                        time.sleep(0.5 * (retry + 1))  # Exponential backoff
                        continue
                    else:
                        return {"error": "MCP Server error: Invalid response format (neither JSON nor SSE)"}
            
            if "error" in mcp_response:
                error_msg = mcp_response['error'].get('message', 'Unknown error')
                error_code = mcp_response['error'].get('code', 'Unknown code')
                error_data = mcp_response['error'].get('data', '')
                
                print(f"DEBUG: MCP Error - Code: {error_code}, Message: {error_msg}, Data: {error_data}")
                
                # Check if this is an initialization error
                if "initialization" in error_msg.lower() or "before initialization" in error_msg.lower():
                    if retry < max_retries - 1:
                        print(f"DEBUG: Initialization error on retry {retry + 1}, waiting and retrying...")
                        time.sleep(0.5 * (retry + 1))  # Exponential backoff
                        continue
                    else:
                        return {"error": f"MCP Server is still initializing. Please try again in a moment."}
                elif error_code == -32602:  # Invalid parameters
                    # Reset session cache on parameter errors in case it's a session issue
                    global _cached_session_id
                    _cached_session_id = None
                    return {"error": f"MCP Parameter Error: {error_msg}. Check the tool parameters and types."}
                else:
                    return {"error": f"MCP Error: {error_msg}"}
            
            # Extract the result from the MCP response
            result = mcp_response.get("result", {}).get("content", [])
            
            # The result should be a list of content items
            if isinstance(result, list) and len(result) > 0:
                # Get the text content from the first item
                content_text = result[0].get("text", "")
                return parse_mcp_response(content_text, tool_name)
            else:
                return {"error": "No content returned from MCP server"}
            
        except requests.exceptions.RequestException as e:
            last_error = f"MCP Server error: {str(e)}"
            if retry < max_retries - 1:
                print(f"DEBUG: Request failed on retry {retry + 1}, waiting and retrying...")
                time.sleep(0.5 * (retry + 1))  # Exponential backoff
                continue
        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            if retry < max_retries - 1:
                print(f"DEBUG: Unexpected error on retry {retry + 1}, waiting and retrying...")
                time.sleep(0.5 * (retry + 1))  # Exponential backoff
                continue
    
    # If we get here, all retries failed
    return {"error": last_error or "Failed to connect to MCP server after multiple retries"}

def parse_mcp_response(response_text, tool_name):
    """
    Parse the JSON response from the MCP server.
    
    Args:
        response_text: The raw response text from the MCP server
        tool_name: The name of the tool that was called
    
    Returns:
        Parsed results in the expected format
    """
    try:
        # Try to parse as JSON first
        try:
            json_data = json.loads(response_text)
            
            # Handle the new JSON format
            if isinstance(json_data, dict):
                # Extract data from the new format
                videos = []
                channels = []
                playlists = []
                
                # Process videos if present
                if "videos" in json_data and isinstance(json_data["videos"], list):
                    for video in json_data["videos"]:
                        videos.append({
                            "title": video.get("title", ""),
                            "channelTitle": video.get("channel", ""),
                            "viewCount": video.get("views", "0"),
                            "likeCount": video.get("likes", "0"),
                            "publishedAt": video.get("published", ""),
                            "url": video.get("url", ""),
                            "description": video.get("description", ""),
                            "videoId": video.get("video_id", ""),
                            "thumbnail": video.get("thumbnail", "")
                        })
                
                # Process channels if present (assuming similar structure)
                if "channels" in json_data and isinstance(json_data["channels"], list):
                    for channel in json_data["channels"]:
                        channels.append({
                            "title": channel.get("title", ""),
                            "subscriberCount": channel.get("subscribers", "0"),
                            "videoCount": channel.get("videos", "0"),
                            "viewCount": channel.get("views", "0"),
                            "publishedAt": channel.get("published", ""),
                            "url": channel.get("url", ""),
                            "description": channel.get("description", ""),
                            "channelId": channel.get("channel_id", ""),
                            "thumbnail": channel.get("thumbnail", "")
                        })
                
                # Process playlists if present (assuming similar structure)
                if "playlists" in json_data and isinstance(json_data["playlists"], list):
                    for playlist in json_data["playlists"]:
                        playlists.append({
                            "title": playlist.get("title", ""),
                            "channelTitle": playlist.get("channel", ""),
                            "videoCount": playlist.get("videos", "0"),
                            "publishedAt": playlist.get("published", ""),
                            "url": playlist.get("url", ""),
                            "description": playlist.get("description", ""),
                            "playlistId": playlist.get("playlist_id", ""),
                            "thumbnail": playlist.get("thumbnail", "")
                        })
                
                # Return results in the expected format
                result = {
                    "query": json_data.get("query", ""),
                    "total_results": json_data.get("total_results", len(videos) + len(channels) + len(playlists))
                }
                
                if tool_name == "search_youtube_videos":
                    result["videos"] = videos
                elif tool_name == "search_youtube_channels":
                    result["channels"] = channels
                elif tool_name == "search_youtube_playlists":
                    result["playlists"] = playlists
                else:  # search_youtube_all
                    result.update({
                        "videos": videos,
                        "channels": channels,
                        "playlists": playlists
                    })
                
                return result
            
        except json.JSONDecodeError:
            # Fall back to old parsing method for backward compatibility
            pass
        
        # Fallback to old parsing method if JSON parsing fails
        # Split the response into lines and parse each section
        lines = response_text.strip().split('\n')
        
        videos = []
        channels = []
        playlists = []
        total_results = 0
        
        # Look for the VIDEOS section
        in_videos_section = False
        in_channels_section = False
        in_playlists_section = False
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
                
            # Check for section headers
            if line.startswith('VIDEOS:'):
                in_videos_section = True
                in_channels_section = False
                in_playlists_section = False
                i += 1
                continue
            elif line.startswith('CHANNELS:'):
                in_videos_section = False
                in_channels_section = True
                in_playlists_section = False
                i += 1
                continue
            elif line.startswith('PLAYLISTS:'):
                in_videos_section = False
                in_channels_section = False
                in_playlists_section = True
                i += 1
                continue
            elif line.startswith('SUMMARY:') or line.startswith('SUCCESS:'):
                # Extract total count if available
                if 'Found' in line and 'results' in line:
                    try:
                        count_text = line.split('Found')[1].split('results')[0].strip()
                        total_results = int(count_text)
                    except:
                        total_results = len(videos) + len(channels) + len(playlists)
                elif 'Videos:' in line:
                    try:
                        # Look for "Videos: X" pattern
                        parts = line.split('Videos:')
                        if len(parts) > 1:
                            video_count = int(parts[1].strip().split()[0])
                            total_results += video_count
                    except:
                        pass
                in_videos_section = False
                in_channels_section = False
                in_playlists_section = False
                i += 1
                continue
            elif line.startswith('ERROR:'):
                return {"error": line.replace('ERROR:', '').strip()}
            
            # Parse video entries (bullet points)
            if in_videos_section and (line.startswith('â¢') or line.startswith('•') or line.startswith('\u2022') or line.startswith('\u2022')):
                video_data = parse_bullet_video(line, lines, i)
                if video_data:
                    videos.append(video_data)
            elif in_channels_section and (line.startswith('â¢') or line.startswith('•') or line.startswith('\u2022')):
                channel_data = parse_bullet_channel(line, lines, i)
                if channel_data:
                    channels.append(channel_data)
            elif in_playlists_section and (line.startswith('â¢') or line.startswith('•') or line.startswith('\u2022')):
                playlist_data = parse_bullet_playlist(line, lines, i)
                if playlist_data:
                    playlists.append(playlist_data)
            
            i += 1
        
        # Return results in the expected format
        if tool_name == "search_youtube_videos":
            return {"videos": videos, "query": "search query"}
        elif tool_name == "search_youtube_channels":
            return {"channels": channels, "query": "search query"}
        elif tool_name == "search_youtube_playlists":
            return {"playlists": playlists, "query": "search query"}
        else:  # search_youtube_all
            return {
                "videos": videos,
                "channels": channels,
                "playlists": playlists,
                "total_results": total_results if total_results > 0 else len(videos) + len(channels) + len(playlists)
            }
            
    except Exception as e:
        return {"error": f"Failed to parse MCP response: {str(e)}"}

def parse_bullet_video(bullet_line, lines, start_index):
    """Parse video information from a bullet point format"""
    try:
        # Extract video title from the bullet line - handle all bullet types
        title = bullet_line.replace('â¢', '').replace('•', '').replace('\u2022', '').strip()
        
        # Initialize default values
        channel_title = ""
        url = ""
        
        # Look for related lines in the next few lines
        i = start_index + 1
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith('â¢') or line.startswith('•') or line.startswith('\u2022') or line.startswith('VIDEOS:') or line.startswith('CHANNELS:') or line.startswith('PLAYLISTS:') or line.startswith('SUMMARY:') or line.startswith('SUCCESS:'):
                break
                
            if line.startswith('Channel:'):
                channel_title = line.replace('Channel:', '').strip()
            elif line.startswith('URL:'):
                url = line.replace('URL:', '').strip()
                break
            i += 1
        
        return {
            "title": title,
            "channelTitle": channel_title,
            "viewCount": "0",  # Not provided in this format
            "likeCount": "0",  # Not provided in this format
            "publishedAt": "",  # Not provided in this format
            "url": url,
            "description": "",  # Not provided in this format
            "videoId": url.split('v=')[-1] if 'v=' in url else "",
            "thumbnail": ""  # Not provided in this format
        }
    except Exception as e:
        print(f"Error parsing bullet video: {e}")
        return None

def parse_bullet_channel(bullet_line, lines, start_index):
    """Parse channel information from a bullet point format"""
    try:
        # Extract channel title from the bullet line
        title = bullet_line.replace('•', '').strip()
        
        # Initialize default values
        url = ""
        
        # Look for related lines in the next few lines
        i = start_index + 1
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith('â¢') or line.startswith('•') or line.startswith('\u2022') or line.startswith('VIDEOS:') or line.startswith('CHANNELS:') or line.startswith('PLAYLISTS:') or line.startswith('SUMMARY:') or line.startswith('SUCCESS:'):
                break
                
            if line.startswith('URL:'):
                url = line.replace('URL:', '').strip()
                break
            i += 1
        
        return {
            "title": title,
            "subscriberCount": "0",  # Not provided in this format
            "videoCount": "0",  # Not provided in this format
            "viewCount": "0",  # Not provided in this format
            "publishedAt": "",  # Not provided in this format
            "url": url,
            "description": "",  # Not provided in this format
            "channelId": url.split('/')[-1] if url else "",
            "thumbnail": ""  # Not provided in this format
        }
    except Exception as e:
        print(f"Error parsing bullet channel: {e}")
        return None

def parse_bullet_playlist(bullet_line, lines, start_index):
    """Parse playlist information from a bullet point format"""
    try:
        # Extract playlist title from the bullet line
        title = bullet_line.replace('•', '').strip()
        
        # Initialize default values
        channel_title = ""
        url = ""
        
        # Look for related lines in the next few lines
        i = start_index + 1
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith('â¢') or line.startswith('•') or line.startswith('\u2022') or line.startswith('VIDEOS:') or line.startswith('CHANNELS:') or line.startswith('PLAYLISTS:') or line.startswith('SUMMARY:') or line.startswith('SUCCESS:'):
                break
                
            if line.startswith('Channel:'):
                channel_title = line.replace('Channel:', '').strip()
            elif line.startswith('URL:'):
                url = line.replace('URL:', '').strip()
                break
            i += 1
        
        return {
            "title": title,
            "channelTitle": channel_title,
            "videoCount": "0",  # Not provided in this format
            "publishedAt": "",  # Not provided in this format
            "url": url,
            "description": "",  # Not provided in this format
            "playlistId": url.split('list=')[-1] if 'list=' in url else "",
            "thumbnail": ""  # Not provided in this format
        }
    except Exception as e:
        print(f"Error parsing bullet playlist: {e}")
        return None

def parse_video_block(lines, start_index):
    """Parse video information from a video block in the MCP response"""
    try:
        # Extract video title from the first line
        title = lines[start_index].replace('VIDEO:', '').strip()
        
        # Initialize default values
        channel_title = ""
        views = "0"
        likes = "0"
        published = ""
        url = ""
        description = ""
        
        # Look for related lines in the next few lines until we hit a separator
        i = start_index + 1
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('---') or line.startswith('VIDEO:') or line.startswith('CHANNEL:') or line.startswith('PLAYLIST:') or line.startswith('SUCCESS:'):
                break
                
            if line.startswith('Channel:'):
                channel_title = line.replace('Channel:', '').strip()
            elif line.startswith('Views:'):
                views = line.replace('Views:', '').strip()
            elif line.startswith('Likes:'):
                likes = line.replace('Likes:', '').strip()
            elif line.startswith('Published:'):
                published = line.replace('Published:', '').strip()
            elif line.startswith('URL:'):
                url = line.replace('URL:', '').strip()
            elif line.startswith('Description:'):
                description = line.replace('Description:', '').strip()
                if description.endswith('...'):
                    description = description[:-3]
                break
            i += 1
        
        return {
            "title": title,
            "channelTitle": channel_title,
            "viewCount": views,
            "likeCount": likes,
            "publishedAt": published,
            "url": url,
            "description": description,
            "videoId": url.split('v=')[-1] if 'v=' in url else "",
            "thumbnail": ""  # Not provided in current MCP response
        }
    except Exception as e:
        print(f"Error parsing video block: {e}")
        return None

def parse_channel_block(lines, start_index):
    """Parse channel information from a channel block in the MCP response"""
    try:
        # Extract channel title from the first line
        title = lines[start_index].replace('CHANNEL:', '').strip()
        
        # Initialize default values
        subscribers = "0"
        videos = "0"
        views = "0"
        created = ""
        url = ""
        description = ""
        
        # Look for related lines in the next few lines until we hit a separator
        i = start_index + 1
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('---') or line.startswith('VIDEO:') or line.startswith('CHANNEL:') or line.startswith('PLAYLIST:') or line.startswith('SUCCESS:'):
                break
                
            if line.startswith('Subscribers:'):
                subscribers = line.replace('Subscribers:', '').strip()
            elif line.startswith('Videos:'):
                videos = line.replace('Videos:', '').strip()
            elif line.startswith('Total Views:'):
                views = line.replace('Total Views:', '').strip()
            elif line.startswith('Created:'):
                created = line.replace('Created:', '').strip()
            elif line.startswith('URL:'):
                url = line.replace('URL:', '').strip()
            elif line.startswith('Description:'):
                description = line.replace('Description:', '').strip()
                if description.endswith('...'):
                    description = description[:-3]
                break
            i += 1
        
        return {
            "title": title,
            "subscriberCount": subscribers,
            "videoCount": videos,
            "viewCount": views,
            "publishedAt": created,
            "url": url,
            "description": description,
            "channelId": url.split('/')[-1] if url else "",
            "thumbnail": ""  # Not provided in current MCP response
        }
    except Exception as e:
        print(f"Error parsing channel block: {e}")
        return None

def parse_playlist_block(lines, start_index):
    """Parse playlist information from a playlist block in the MCP response"""
    try:
        # Extract playlist title from the first line
        title = lines[start_index].replace('PLAYLIST:', '').strip()
        
        # Initialize default values
        channel_title = ""
        video_count = "0"
        created = ""
        url = ""
        description = ""
        
        # Look for related lines in the next few lines until we hit a separator
        i = start_index + 1
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('---') or line.startswith('VIDEO:') or line.startswith('CHANNEL:') or line.startswith('PLAYLIST:') or line.startswith('SUCCESS:'):
                break
                
            if line.startswith('Channel:'):
                channel_title = line.replace('Channel:', '').strip()
            elif line.startswith('Videos:'):
                video_count = line.replace('Videos:', '').strip()
            elif line.startswith('Created:'):
                created = line.replace('Created:', '').strip()
            elif line.startswith('URL:'):
                url = line.replace('URL:', '').strip()
            elif line.startswith('Description:'):
                description = line.replace('Description:', '').strip()
                if description.endswith('...'):
                    description = description[:-3]
                break
            i += 1
        
        return {
            "title": title,
            "channelTitle": channel_title,
            "videoCount": video_count,
            "publishedAt": created,
            "url": url,
            "description": description,
            "playlistId": url.split('list=')[-1] if 'list=' in url else "",
            "thumbnail": ""  # Not provided in current MCP response
        }
    except Exception as e:
        print(f"Error parsing playlist block: {e}")
        return None

@app.route('/')
def index():
    query = request.args.get('q', 'Model Context Protocol')
    
    # Get search results from MCP server
    search_results = call_mcp_tool("search_youtube_all", {
        "query": str(query),
        "max_results": int(25)
    })
    
    if "error" in search_results:
        return render_template('index.html', 
                             error=search_results["error"],
                             query=query,
                             videos=[], 
                             channels=[], 
                             playlists=[],
                             total_results=0)
    
    # Format results for template - data is already in the correct format from parse_mcp_response
    videos = search_results.get("videos", [])
    channels = search_results.get("channels", [])
    playlists = search_results.get("playlists", [])
    
    template_values = {
        'videos': videos,
        'channels': channels,
        'playlists': playlists,
        'query': query,
        'total_results': search_results.get("total_results", 0)
    }
    
    return render_template('index.html', **template_values)

@app.route('/search')
def search():
    query = request.args.get('q', 'Model Context Protocol')
    content_type = request.args.get('type', 'all')
    
    if content_type == 'videos':
        results = call_mcp_tool("search_youtube_videos", {
            "query": str(query),
            "max_results": int(25)
        })
        return jsonify({"videos": results, "query": query})
    
    elif content_type == 'channels':
        results = call_mcp_tool("search_youtube_channels", {
            "query": str(query),
            "max_results": int(25)
        })
        return jsonify({"channels": results, "query": query})
    
    elif content_type == 'playlists':
        results = call_mcp_tool("search_youtube_playlists", {
            "query": str(query),
            "max_results": int(25)
        })
        return jsonify({"playlists": results, "query": query})
    
    else:  # all
        results = call_mcp_tool("search_youtube_all", {
            "query": str(query),
            "max_results": int(25)
        })
        print(f"DEBUG: Search results for '{query}': {results}")
        return jsonify(results)

@app.route('/health')
def health():
    """Health check endpoint to verify MCP server connectivity."""
    try:
        url = f"{MCP_SERVER_URL}/mcp"
        session_id = get_or_create_session_id()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "mcp-protocol-version": PROTOCOL_VERSION,
        }
        if session_id:
            headers["mcp-session-id"] = session_id
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        # Debug: Log the tools/list request
        print(f"DEBUG: Sending tools/list request: {json.dumps(mcp_request, indent=2)}")
        response = requests.post(url, json=mcp_request, headers=headers, timeout=5)
        if response.status_code == 200:
            # Check if response is empty
            if not response.text.strip():
                return jsonify({
                    "status": "unhealthy", 
                    "mcp_server": "empty_response",
                    "error": "Server returned empty response (may still be initializing)",
                    "server_url": MCP_SERVER_URL
                })
            
            try:
                mcp_response = response.json()
            except json.JSONDecodeError:
                # Try SSE format
                mcp_response = parse_sse_response(response.text)
                if mcp_response is None:
                    return jsonify({
                        "status": "unhealthy", 
                        "mcp_server": "invalid_response",
                        "error": "Server returned invalid response format (neither JSON nor SSE)",
                        "server_url": MCP_SERVER_URL
                    })
            
            if "error" in mcp_response:
                error_msg = mcp_response['error'].get('message', 'Unknown error')
                if "initialization" in error_msg.lower() or "before initialization" in error_msg.lower():
                    return jsonify({
                        "status": "unhealthy", 
                        "mcp_server": "initializing",
                        "error": "Server is still initializing",
                        "server_url": MCP_SERVER_URL
                    })
                else:
                    return jsonify({
                        "status": "unhealthy", 
                        "mcp_server": "error",
                        "error": error_msg,
                        "server_url": MCP_SERVER_URL
                    })
            tools = mcp_response.get("result", {}).get("tools", [])
            available_tools = len(tools) if isinstance(tools, list) else 0
            return jsonify({
                "status": "healthy", 
                "mcp_server": "connected",
                "available_tools": available_tools,
                "server_url": MCP_SERVER_URL,
                "tools": [tool.get("name", "Unknown") for tool in tools[:5]]
            })
        else:
            return jsonify({
                "status": "unhealthy", 
                "mcp_server": "unreachable",
                "status_code": response.status_code,
                "server_url": MCP_SERVER_URL
            })
    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "unhealthy", 
            "mcp_server": "connection_failed",
            "error": str(e),
            "server_url": MCP_SERVER_URL
        })

@app.route('/debug')
def debug():
    """Debug endpoint to test MCP connectivity and tools listing."""
    try:
        url = f"{MCP_SERVER_URL}/mcp"
        session_id = get_or_create_session_id()
        
        if not session_id:
            return jsonify({
                "error": "Failed to initialize MCP session",
                "mcp_server_url": MCP_SERVER_URL
            })
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "mcp-protocol-version": PROTOCOL_VERSION,
            "mcp-session-id": session_id
        }
        
        # Test tools/list
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/list",
            "params": {}
        }
        
        print(f"DEBUG: Using session ID: {session_id}")
        print(f"DEBUG: Headers: {headers}")
        
        response = requests.post(url, json=mcp_request, headers=headers, timeout=10)
        raw_response = response.text
        
        # Try to parse response
        try:
            mcp_response = response.json()
        except json.JSONDecodeError:
            mcp_response = parse_sse_response(response.text)
        
        return jsonify({
            "status_code": response.status_code,
            "raw_response": raw_response,
            "parsed_response": mcp_response,
            "headers": dict(response.headers),
            "request_sent": mcp_request,
            "session_id_used": session_id,
            "request_headers": headers
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "mcp_server_url": MCP_SERVER_URL
        })

@app.route('/reset-session')
def reset_session():
    """Reset the cached MCP session to force re-initialization."""
    global _cached_session_id
    _cached_session_id = None
    return jsonify({"message": "MCP session cache cleared", "status": "success"})

@app.route('/status')
def status():
    """Get MCP server connection status."""
    try:
        # Try to get or create a session to test connectivity
        session_id = get_or_create_session_id()
        
        if session_id:
            return jsonify({
                "status": "connected",
                "message": "MCP Server Connected",
                "session_id": session_id[:8] + "..." if session_id else None,
                "server_url": MCP_SERVER_URL
            })
        else:
            return jsonify({
                "status": "disconnected", 
                "message": "MCP Server Disconnected",
                "server_url": MCP_SERVER_URL
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Connection Error: {str(e)}",
            "server_url": MCP_SERVER_URL
        })

if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"Starting YouTube Search via MCP on {host}:{port}")
    print(f"MCP Server URL: {MCP_SERVER_URL}")
    print("Available endpoints:")
    print("- GET /: Main search page")
    print("- GET /search?q=query&type=all|videos|channels|playlists: API endpoint")
    print("- GET /status: MCP server connection status")
    print("- GET /health: Health check")
    print("- GET /debug: Debug MCP connectivity and tools")
    print("- GET /reset-session: Clear MCP session cache")
    
    app.run(debug=debug, host=host, port=port)
