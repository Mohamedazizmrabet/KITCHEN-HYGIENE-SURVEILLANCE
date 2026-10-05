import urllib.request
import os

url = "https://www.w3schools.com/html/mov_bbb.mp4" # Big Buck Bunny - just a fallback if we can't find a kitchen one
# Wait, let's use a known public sample video from pexels (people walking)
url = "https://static.videezy.com/system/resources/previews/000/004/302/original/1.mp4"
filepath = "C:/Users/aziz4/Desktop/trainF/test_video.mp4"

print("Downloading test video...")
try:
    urllib.request.urlretrieve(url, filepath)
    print("Downloaded to:", filepath)
except Exception as e:
    print("Error:", e)
