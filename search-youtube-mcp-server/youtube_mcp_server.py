#!/usr/bin/env python3
"""
YouTube MCP Server for YouTube search functionality
This implements the Model Context Protocol with structured JSON responses
"""

import os
import asyncio
import argparse
from typing import Any, Dict
from dotenv import load_dotenv
from fastmcp import FastMCP
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

# Initialize YouTube API
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', 'REPLACE_ME')
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# Server configuration
HOST = os.getenv('MCP_HOST', '127.0.0.1')
PORT = int(os.getenv('MCP_PORT', '8000'))

# Create FastMCP instance
mcp = FastMCP("youtube-search-mcp-server")

# Server initialization state
_server_initialized = False
_initialization_lock = asyncio.Lock()

async def ensure_server_initialized():
    """Ensure server is properly initialized before processing requests"""
    global _server_initialized
    async with _initialization_lock:
        if not _server_initialized:
            # Small delay to allow server startup to complete
            await asyncio.sleep(0.5)
            _server_initialized = True

async def check_initialization():
    """Check if server is initialized and return appropriate error if not"""
    if not _server_initialized:
        return "ERROR: Server is still initializing, please try again in a moment."
    return None

async def search_youtube_videos_data(query: str, max_results: int, order: str) -> Dict[str, Any]:
    """Search YouTube videos and return structured data"""
    # Check initialization first
    init_error = await check_initialization()
    if init_error:
        return {"error": init_error}
        
    await ensure_server_initialized()
    
    if YOUTUBE_API_KEY == "REPLACE_ME":
        return {"error": "YouTube API key not configured. Please set YOUTUBE_API_KEY in your .env file."}
    
    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY)
        
        search_response = youtube.search().list(
            q=query,
            part="id,snippet",
            maxResults=max_results,
            type="video",
            order=order
        ).execute()
        
        videos = []
        for search_result in search_response.get("items", []):
            if search_result["id"]["kind"] == "youtube#video":
                video_id = search_result["id"]["videoId"]
                
                # Get detailed video information
                try:
                    video_response = youtube.videos().list(
                        part="statistics,snippet",
                        id=video_id
                    ).execute()
                    
                    if video_response.get("items"):
                        video_info = video_response["items"][0]
                        view_count = video_info["statistics"].get("viewCount", "0")
                        like_count = video_info["statistics"].get("likeCount", "0")
                        
                        # Safe number formatting
                        try:
                            view_count_formatted = f"{int(view_count):,}" if view_count.isdigit() else view_count
                            like_count_formatted = f"{int(like_count):,}" if like_count.isdigit() else like_count
                        except (ValueError, AttributeError):
                            view_count_formatted = view_count
                            like_count_formatted = like_count
                        
                        video_data = {
                            "title": search_result["snippet"]["title"],
                            "channel": search_result["snippet"]["channelTitle"],
                            "views": view_count_formatted,
                            "likes": like_count_formatted,
                            "published": search_result["snippet"]["publishedAt"][:10],
                            "url": f"https://www.youtube.com/watch?v={video_id}",
                            "description": search_result["snippet"]["description"][:200] + "...",
                            "video_id": video_id,
                            "thumbnail": search_result["snippet"]["thumbnails"].get("medium", {}).get("url", "")
                        }
                    else:
                        # Fallback without statistics
                        video_data = {
                            "title": search_result["snippet"]["title"],
                            "channel": search_result["snippet"]["channelTitle"],
                            "published": search_result["snippet"]["publishedAt"][:10],
                            "url": f"https://www.youtube.com/watch?v={video_id}",
                            "description": search_result["snippet"]["description"][:200] + "...",
                            "video_id": video_id,
                            "thumbnail": search_result["snippet"]["thumbnails"].get("medium", {}).get("url", "")
                        }
                        
                except HttpError:
                    # Fallback without statistics
                    video_data = {
                        "title": search_result["snippet"]["title"],
                        "channel": search_result["snippet"]["channelTitle"],
                        "published": search_result["snippet"]["publishedAt"][:10],
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "description": search_result["snippet"]["description"][:200] + "...",
                        "video_id": video_id,
                        "thumbnail": search_result["snippet"]["thumbnails"].get("medium", {}).get("url", "")
                    }
                
                videos.append(video_data)
        
        return {
            "query": query,
            "total_results": len(videos),
            "videos": videos,
            "search_parameters": {
                "max_results": max_results,
                "order": order
            }
        }
            
    except HttpError as e:
        return {"error": f"YouTube API error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

async def search_youtube_channels_data(query: str, max_results: int, order: str) -> Dict[str, Any]:
    """Search YouTube channels and return structured data"""
    # Check initialization first
    init_error = await check_initialization()
    if init_error:
        return {"error": init_error}
        
    await ensure_server_initialized()
    
    if YOUTUBE_API_KEY == "REPLACE_ME":
        return {"error": "YouTube API key not configured. Please set YOUTUBE_API_KEY in your .env file."}
    
    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY)
        
        search_response = youtube.search().list(
            q=query,
            part="id,snippet",
            maxResults=max_results,
            type="channel",
            order=order
        ).execute()
        
        channels = []
        for search_result in search_response.get("items", []):
            if search_result["id"]["kind"] == "youtube#channel":
                channel_id = search_result["id"]["channelId"]
                
                try:
                    channel_response = youtube.channels().list(
                        part="statistics,snippet",
                        id=channel_id
                    ).execute()
                    
                    if channel_response.get("items"):
                        channel_info = channel_response["items"][0]
                        subscriber_count = channel_info["statistics"].get("subscriberCount", "0")
                        video_count = channel_info["statistics"].get("videoCount", "0")
                        view_count = channel_info["statistics"].get("viewCount", "0")
                        
                        # Safe number formatting
                        try:
                            subscriber_count_formatted = f"{int(subscriber_count):,}" if subscriber_count.isdigit() else subscriber_count
                            video_count_formatted = f"{int(video_count):,}" if video_count.isdigit() else video_count
                            view_count_formatted = f"{int(view_count):,}" if view_count.isdigit() else view_count
                        except (ValueError, AttributeError):
                            subscriber_count_formatted = subscriber_count
                            video_count_formatted = video_count
                            view_count_formatted = view_count
                        
                        channel_data = {
                            "title": search_result["snippet"]["title"],
                            "subscribers": subscriber_count_formatted,
                            "videos": video_count_formatted,
                            "total_views": view_count_formatted,
                            "created": search_result["snippet"]["publishedAt"][:10],
                            "url": f"https://www.youtube.com/channel/{channel_id}",
                            "description": search_result["snippet"]["description"][:200] + "...",
                            "channel_id": channel_id,
                            "thumbnail": search_result["snippet"]["thumbnails"].get("medium", {}).get("url", "")
                        }
                        
                except HttpError:
                    channel_data = {
                        "title": search_result["snippet"]["title"],
                        "created": search_result["snippet"]["publishedAt"][:10],
                        "url": f"https://www.youtube.com/channel/{channel_id}",
                        "description": search_result["snippet"]["description"][:200] + "...",
                        "channel_id": channel_id,
                        "thumbnail": search_result["snippet"]["thumbnails"].get("medium", {}).get("url", "")
                    }
                
                channels.append(channel_data)
        
        return {
            "query": query,
            "total_results": len(channels),
            "channels": channels,
            "search_parameters": {
                "max_results": max_results,
                "order": order
            }
        }
            
    except HttpError as e:
        return {"error": f"YouTube API error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

async def search_youtube_playlists_data(query: str, max_results: int, order: str) -> Dict[str, Any]:
    """Search YouTube playlists and return structured data"""
    # Check initialization first
    init_error = await check_initialization()
    if init_error:
        return {"error": init_error}
        
    await ensure_server_initialized()
    
    if YOUTUBE_API_KEY == "REPLACE_ME":
        return {"error": "YouTube API key not configured. Please set YOUTUBE_API_KEY in your .env file."}
    
    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY)
        
        search_response = youtube.search().list(
            q=query,
            part="id,snippet",
            maxResults=max_results,
            type="playlist",
            order=order
        ).execute()
        
        playlists = []
        for search_result in search_response.get("items", []):
            if search_result["id"]["kind"] == "youtube#playlist":
                playlist_id = search_result["id"]["playlistId"]
                
                try:
                    playlist_response = youtube.playlists().list(
                        part="snippet,contentDetails",
                        id=playlist_id
                    ).execute()
                    
                    if playlist_response.get("items"):
                        playlist_info = playlist_response["items"][0]
                        video_count = playlist_info["contentDetails"]["itemCount"]
                        
                        playlist_data = {
                            "title": search_result["snippet"]["title"],
                            "channel": search_result["snippet"]["channelTitle"],
                            "video_count": video_count,
                            "created": search_result["snippet"]["publishedAt"][:10],
                            "url": f"https://www.youtube.com/playlist?list={playlist_id}",
                            "description": search_result["snippet"]["description"][:200] + "...",
                            "playlist_id": playlist_id,
                            "thumbnail": search_result["snippet"]["thumbnails"].get("medium", {}).get("url", "")
                        }
                        
                except HttpError:
                    playlist_data = {
                        "title": search_result["snippet"]["title"],
                        "channel": search_result["snippet"]["channelTitle"],
                        "created": search_result["snippet"]["publishedAt"][:10],
                        "url": f"https://www.youtube.com/playlist?list={playlist_id}",
                        "description": search_result["snippet"]["description"][:200] + "...",
                        "playlist_id": playlist_id,
                        "thumbnail": search_result["snippet"]["thumbnails"].get("medium", {}).get("url", "")
                    }
                
                playlists.append(playlist_data)
        
        return {
            "query": query,
            "total_results": len(playlists),
            "playlists": playlists,
            "search_parameters": {
                "max_results": max_results,
                "order": order
            }
        }
            
    except HttpError as e:
        return {"error": f"YouTube API error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

async def search_youtube_all_data(query: str, max_results: int, order: str) -> Dict[str, Any]:
    """Search all YouTube content types and return structured data"""
    # Check initialization first
    init_error = await check_initialization()
    if init_error:
        return {"error": init_error}
        
    await ensure_server_initialized()
    
    if YOUTUBE_API_KEY == "REPLACE_ME":
        return {"error": "YouTube API key not configured. Please set YOUTUBE_API_KEY in your .env file."}
    
    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY)
        
        # Calculate results per type (distribute max_results across all types)
        results_per_type = max(1, max_results // 3)  # At least 1 result per type
        
        videos = []
        channels = []
        playlists = []
        
        # Search for videos
        try:
            video_search = youtube.search().list(
                q=query,
                part="id,snippet",
                maxResults=results_per_type,
                type="video",
                order=order
            ).execute()
            
            for search_result in video_search.get("items", []):
                if search_result["id"]["kind"] == "youtube#video":
                    video_id = search_result["id"]["videoId"]
                    video_data = {
                        "title": search_result["snippet"]["title"],
                        "channel": search_result["snippet"]["channelTitle"],
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "video_id": video_id,
                        "thumbnail": search_result["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
                        "published": search_result["snippet"]["publishedAt"][:10]
                    }
                    videos.append(video_data)
        except HttpError as e:
            print(f"Error searching videos: {e}")
        
        # Search for channels
        try:
            channel_search = youtube.search().list(
                q=query,
                part="id,snippet",
                maxResults=results_per_type,
                type="channel",
                order=order
            ).execute()
            
            for search_result in channel_search.get("items", []):
                if search_result["id"]["kind"] == "youtube#channel":
                    channel_id = search_result["id"]["channelId"]
                    channel_data = {
                        "title": search_result["snippet"]["title"],
                        "url": f"https://www.youtube.com/channel/{channel_id}",
                        "channel_id": channel_id,
                        "thumbnail": search_result["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
                        "created": search_result["snippet"]["publishedAt"][:10]
                    }
                    channels.append(channel_data)
        except HttpError as e:
            print(f"Error searching channels: {e}")
        
        # Search for playlists
        try:
            playlist_search = youtube.search().list(
                q=query,
                part="id,snippet",
                maxResults=results_per_type,
                type="playlist",
                order=order
            ).execute()
            
            for search_result in playlist_search.get("items", []):
                if search_result["id"]["kind"] == "youtube#playlist":
                    playlist_id = search_result["id"]["playlistId"]
                    playlist_data = {
                        "title": search_result["snippet"]["title"],
                        "channel": search_result["snippet"]["channelTitle"],
                        "url": f"https://www.youtube.com/playlist?list={playlist_id}",
                        "playlist_id": playlist_id,
                        "thumbnail": search_result["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
                        "created": search_result["snippet"]["publishedAt"][:10]
                    }
                    playlists.append(playlist_data)
        except HttpError as e:
            print(f"Error searching playlists: {e}")
        
        return {
            "query": query,
            "total_results": len(videos) + len(channels) + len(playlists),
            "summary": {
                "videos": len(videos),
                "channels": len(channels),
                "playlists": len(playlists)
            },
            "videos": videos,
            "channels": channels,
            "playlists": playlists,
            "search_parameters": {
                "max_results": max_results,
                "order": order,
                "results_per_type": results_per_type
            }
        }
        
    except HttpError as e:
        return {"error": f"YouTube API error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

# Define MCP tools
@mcp.tool()
async def search_youtube_videos(query: str, max_results: int = 10, order: str = "relevance") -> Dict[str, Any]:
    """Search for YouTube videos and return structured JSON data"""
    return await search_youtube_videos_data(query, max_results, order)

@mcp.tool()
async def search_youtube_channels(query: str, max_results: int = 10, order: str = "relevance") -> Dict[str, Any]:
    """Search for YouTube channels and return structured JSON data"""
    return await search_youtube_channels_data(query, max_results, order)

@mcp.tool()
async def search_youtube_playlists(query: str, max_results: int = 10, order: str = "relevance") -> Dict[str, Any]:
    """Search for YouTube playlists and return structured JSON data"""
    return await search_youtube_playlists_data(query, max_results, order)

@mcp.tool()
async def search_youtube_all(query: str, max_results: int = 25, order: str = "relevance") -> Dict[str, Any]:
    """Search for all YouTube content types and return structured JSON data"""
    return await search_youtube_all_data(query, max_results, order)

def parse_arguments():
    """Parse command line arguments for server mode"""
    parser = argparse.ArgumentParser(
        description="YouTube Search MCP Server - Returns structured JSON data"
    )
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="http",
        help="Server mode: stdio (for direct MCP clients) or http (for MCP Inspector) [default: http]"
    )
    parser.add_argument(
        "--host",
        default=HOST,
        help=f"HTTP server host [default: {HOST}]"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=PORT,
        help=f"HTTP server port [default: {PORT}]"
    )
    return parser.parse_args()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Update server configuration based on arguments
    if args.mode == "http":
        HOST = args.host
        PORT = args.port
    
    # Run the MCP server
    print("STARTING: YouTube Search MCP Server...")
    print(f"MODE: {args.mode.upper()}")
    
    if args.mode == "http":
        print(f"SERVER: Running HTTP server on http://{HOST}:{PORT}")
        print(f"MCP INSPECTOR CONNECTION:")
        print(f"  URL: http://{HOST}:{PORT}")
        print(f"  Host: {HOST}")
        print(f"  Port: {PORT}")
        print(f"  Mode: HTTP (returns structured JSON data)")
    else:
        print("MODE: stdio (for direct MCP client connections)")
        print("INFO: Use this mode with MCP clients that support stdio transport")
    
    print("\nAVAILABLE TOOLS:")
    print("  • search_youtube_videos")
    print("  • search_youtube_channels") 
    print("  • search_youtube_playlists")
    print("  • search_youtube_all")
    print("\nCONFIG: Make sure YOUTUBE_API_KEY is set in your .env file")
    print("INFO: This server implements the Model Context Protocol with structured JSON responses")
    
    # Run the server in the selected mode
    if args.mode == "http":
        # Run the FastMCP server with HTTP support
        print(f"\nStarting HTTP server on {HOST}:{PORT}...")
        async def run_http_server():
            await ensure_server_initialized()
            await mcp.run_streamable_http_async(host=HOST, port=PORT)
        asyncio.run(run_http_server())
    else:
        # Run in stdio mode for direct MCP client connections
        print("\nSTDIO MODE: Server is ready for stdio connections")
        print("INFO: Connect your MCP client to stdin/stdout")
        async def run_stdio_server():
            await ensure_server_initialized()
            await mcp.run_stdio_async()
        asyncio.run(run_stdio_server())
