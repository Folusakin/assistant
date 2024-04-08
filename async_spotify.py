#async_spotify.py

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from contextlib import asynccontextmanager
import sys
import asyncio
import os

# Set event loop policy on Windows for Python 3.8+
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
class AsyncSpotifyClient:
    def __init__(self):
        self.username = os.environ.get('SPOTIFY_USERNAME')  # Replace with environment variable
        self.clientID = os.environ.get('SPOTIFY_CLIENT_ID')  # Replace with environment variable
        self.clientSecret = os.environ.get('SPOTIFY_CLIENT_SECRET')  # Replace with environment variable
        self.redirect_uri = 'http://google.com/callback/'
        self.scope = 'user-modify-playback-state user-read-playback-state user-read-currently-playing playlist-read-private playlist-modify-public playlist-modify-private'
        self.device_id = None
        self.oauth_object = SpotifyOAuth(self.clientID, self.clientSecret, self.redirect_uri, scope=self.scope)

    def authenticate_client(self):
        token_dict = self.oauth_object.get_cached_token()
        if token_dict is None:
            print("No valid token available; redirecting for authorization.")
            # Directly get a new token if no cached token is available
            token_dict = self.oauth_object.get_access_token()
        elif self.oauth_object.is_token_expired(token_dict):
            print("Token expired; refreshing.")
            # Refresh the token if it's expired
            token_dict = self.oauth_object.refresh_access_token(token_dict['refresh_token'])
        return spotipy.Spotify(auth=token_dict['access_token'])

    async def async_init(self):
        self.spotifyObject = self.authenticate_client()
        devices = self.spotifyObject.devices()
        for device in devices.get('devices', []):
            if device.get('name') == "Your Speaker":
                self.device_id = device.get('id')
                break

        if not self.device_id:
            raise Exception("Device not active or Speaker type device not found.")
        await self.start_token_refresh_loop()  # Ensure this method is awaited

    async def token_refresh_loop(self):
        while True:
            await asyncio.sleep(1800)  # Sleep for 1 hour
            self.spotifyObject = self.authenticate_client()
            print("Spotify token refreshed")

    async def start_token_refresh_loop(self):
        asyncio.create_task(self.token_refresh_loop())

    async def display_user_info(self):
        user_info = await asyncio.to_thread(self.spotifyObject.current_user)
        return user_info

    async def get_user_details(self):
        user_details = await asyncio.to_thread(self.spotifyObject.me)
        return user_details

    async def create_playlist(self, name, public=True, description=''):
        existing_playlists = await asyncio.to_thread(self.spotifyObject.current_user_playlists)
        for playlist in existing_playlists.get('items', []):
            if playlist['name'] == name:
                return {"status": "Playlist already exists", "playlist_id": playlist['id']}
        return await asyncio.to_thread(self.spotifyObject.user_playlist_create, self.username, name, public, description)

    async def add_tracks_to_playlist(self, playlist_name, track_names):
        playlists = await asyncio.to_thread(self.spotifyObject.current_user_playlists)
        playlist_id = None
        for playlist in playlists.get('items', []):
            if playlist['name'] == playlist_name:
                playlist_id = playlist['id']
                break
        if not playlist_id:
            return {"status": "Playlist not found"}

        track_uris = []
        for track_name in track_names:
            results = self.spotifyObject.search(q=f"track:{track_name}", type="track")
            items = results.get('tracks', {}).get('items', [])
            if items:
                track_uris.append(items[0]['uri'])

        if track_uris:
            return await asyncio.to_thread(self.spotifyObject.user_playlist_add_tracks, self.username, playlist_id, track_uris)
        return {"status": "No tracks found"}

    async def get_user_playlists(self, limit=20):
        playlists = await asyncio.to_thread(self.spotifyObject.user_playlists, self.username, limit)
        return playlists

    async def pause_playback(self):
        try:
            await asyncio.to_thread(self.spotifyObject.pause_playback, device_id=self.device_id)
            return {"status": "Successfully paused the song"}
        except Exception as e:
            # Log the error or handle it as needed
            return {"status": "Failed to pause the song"}

    async def start_playback(self, playlist_name=None):
        try:
            if playlist_name:
                playlists = await asyncio.to_thread(self.spotifyObject.current_user_playlists)
                playlist_id = None
                for playlist in playlists.get('items', []):
                    if playlist['name'] == playlist_name:
                        playlist_id = playlist['id']
                        break
                if playlist_id:
                    await asyncio.to_thread(self.spotifyObject.start_playback, device_id=self.device_id, context_uri=f'spotify:playlist:{playlist_id}')
                else:
                    return {"status": "Failed to play song, playlist not found"}
            else:
                await asyncio.to_thread(self.spotifyObject.start_playback, device_id=self.device_id)
            return {"status": "Successfully started the playback"}
        except Exception as e:
            # Log the error or handle it as needed
            return {"status": "Failed to play song"}


    async def search_and_play_song(self, song_name, artist_name=None):
        async def async_search_song(query):
            def search():
                results = self.spotifyObject.search(query, limit=50, type="track")
                return results.get('tracks', {}).get('items', [])
            return await asyncio.to_thread(search)

        query = f"track:{song_name}"
        if artist_name:
            query += f" artist:{artist_name}"
        
        song_items = await async_search_song(query)

        if not song_items and artist_name:
            query = f"{song_name} {artist_name}"
            song_items = await async_search_song(query)

        if song_items:
            song = song_items[0]
            song_uri = song['uri']
            song_name = song['name']
            artist_names = ', '.join(artist['name'] for artist in song['artists'])
            await asyncio.to_thread(self.spotifyObject.start_playback, device_id=self.device_id, uris=[song_uri])
            return {"song_name": song_name, "artist_name": artist_names, "status": "Playing successfully"}
        
        return {"song_name": song_name, "artist_name": artist_name if artist_name else "", "status": "Could not find song"}

async def main():
    client = AsyncSpotifyClient()
    await client.setup()

    user_info_task = client.display_user_info()
    search_and_play_task = client.search_and_play_song("Happiness", "Ahssake")

    user_info, search_and_play_result = await asyncio.gather(user_info_task, search_and_play_task)
    print(f"{user_info} \n\n {search_and_play_result}")

    await asyncio.sleep(10)  # Properly use asyncio.sleep instead of time.sleep
    await client.pause_playback()
    print("Playback paused.")

    await asyncio.sleep(10)
    await client.start_playback("I like")  # Example for starting playback of a specific playlist by name
    print("Playback started.")

if __name__ == "__main__":
    asyncio.run(main())
