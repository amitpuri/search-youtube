import os
import urllib
from flask import Flask, render_template, request, jsonify
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Get API key from environment variable
DEVELOPER_KEY = os.getenv('YOUTUBE_API_KEY', 'REPLACE_ME')
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

@app.route('/')
def index():
    query = request.args.get('q', 'Model Context Protocol')
    
    if DEVELOPER_KEY == "REPLACE_ME":
        return "You must set up a project and get an API key to run this project. Please visit <landing page> to do so."
    
    youtube = build(
        YOUTUBE_API_SERVICE_NAME, 
        YOUTUBE_API_VERSION, 
        developerKey=DEVELOPER_KEY)
    
    # Try multiple search strategies to get more diverse results
    all_videos = []
    all_channels = []
    all_playlists = []
    
    # Search 1: General search
    search_response = youtube.search().list(
        q=query,
        part="id,snippet",
        maxResults=25,
        type="video,channel,playlist"
    ).execute()
    
    for search_result in search_response.get("items", []):
        if search_result["id"]["kind"] == "youtube#video":
            all_videos.append("%s (%s)" % (search_result["snippet"]["title"], 
                search_result["id"]["videoId"]))
        elif search_result["id"]["kind"] == "youtube#channel":
            all_channels.append("%s (%s)" % (search_result["snippet"]["title"], 
                search_result["id"]["channelId"]))
        elif search_result["id"]["kind"] == "youtube#playlist":
            all_playlists.append("%s (%s)" % (search_result["snippet"]["title"], 
                search_result["id"]["playlistId"]))
    
    # Search 2: Channel-specific search
    if len(all_channels) < 3:
        channel_search = youtube.search().list(
            q=query + " channel",
            part="id,snippet",
            maxResults=10,
            type="channel"
        ).execute()
        
        for search_result in channel_search.get("items", []):
            if search_result["id"]["kind"] == "youtube#channel":
                channel_str = "%s (%s)" % (search_result["snippet"]["title"], 
                    search_result["id"]["channelId"])
                if channel_str not in all_channels:
                    all_channels.append(channel_str)
    
    # Search 3: Playlist-specific search
    if len(all_playlists) < 3:
        playlist_search = youtube.search().list(
            q=query + " playlist",
            part="id,snippet",
            maxResults=10,
            type="playlist"
        ).execute()
        
        for search_result in playlist_search.get("items", []):
            if search_result["id"]["kind"] == "youtube#playlist":
                playlist_str = "%s (%s)" % (search_result["snippet"]["title"], 
                    search_result["id"]["playlistId"])
                if playlist_str not in all_playlists:
                    all_playlists.append(playlist_str)
    
    template_values = {
        'videos': all_videos[:10],  # Limit to top 10
        'channels': all_channels[:10],  # Limit to top 10
        'playlists': all_playlists[:10],  # Limit to top 10
        'query': query
    }
    
    return render_template('index.html', **template_values)

@app.route('/search')
def search():
    query = request.args.get('q', 'Model Context Protocol')
    
    if DEVELOPER_KEY == "REPLACE_ME":
        return jsonify({"error": "API key not configured"})
    
    youtube = build(
        YOUTUBE_API_SERVICE_NAME, 
        YOUTUBE_API_VERSION, 
        developerKey=DEVELOPER_KEY)
    
    search_response = youtube.search().list(
        q=query,
        part="id,snippet",
        maxResults=25,
        type="video,channel,playlist"
    ).execute()
    
    videos = []
    channels = []
    playlists = []
    
    for search_result in search_response.get("items", []):
        if search_result["id"]["kind"] == "youtube#video":
            videos.append({
                "title": search_result["snippet"]["title"],
                "videoId": search_result["id"]["videoId"],
                "description": search_result["snippet"]["description"]
            })
        elif search_result["id"]["kind"] == "youtube#channel":
            channels.append({
                "title": search_result["snippet"]["title"],
                "channelId": search_result["id"]["channelId"],
                "description": search_result["snippet"]["description"]
            })
        elif search_result["id"]["kind"] == "youtube#playlist":
            playlists.append({
                "title": search_result["snippet"]["title"],
                "playlistId": search_result["id"]["playlistId"],
                "description": search_result["snippet"]["description"]
            })
    
    return jsonify({
        'videos': videos,
        'channels': channels,
        'playlists': playlists
    })

if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    app.run(debug=debug, host=host, port=port)
