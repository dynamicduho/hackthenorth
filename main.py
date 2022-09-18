import re
from flask import Flask, request, render_template
from configure import assemblyai_auth_key as AUTH
import yt_dlp
import requests
from time import sleep
import random
import json
from moviepy.editor import *

app = Flask(  # Create a flask app
    __name__,
    template_folder='templates',
    static_folder='static')

# mp4 formattings opts
ydl_opts_mp4 = {
    'outtmpl': "./%(id)s.%(ext)s",
    'ffmpeg-location': './',
    'format': 'best[ext=mp4]'
}

# mp3 formatting opts
ydl_opts_mp3 = {
    'format':
    'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'ffmpeg-location':
    './',
    'outtmpl':
    "./%(id)s.%(ext)s",
}

# assembly ai api endpoints
transcript_endpoint = "https://api.assemblyai.com/v2/transcript"
upload_endpoint = 'https://api.assemblyai.com/v2/upload'

# auth headers
headers_auth_only = {'authorization': AUTH}
headers = {"authorization": AUTH, "content-type": "application/json"}
CHUNK_SIZE = 5242880

# video source link
link = "https://www.youtube.com/watch?v=aWyn8QS74EY"


def download_video(link):
    _id = link.strip()  # remove prefix and get video id from youtube vid

    # download youtube video as mp3 file as specified by ydl_opts
    def get_vid(_id):
        with yt_dlp.YoutubeDL(ydl_opts_mp4) as ydl:
            return ydl.extract_info(_id)

    meta = get_vid(
        _id)  #creates yt download object and returns the metadata of the vid
    save_location = meta['id'] + ".mp4"
    print('Saved mp4 to', save_location)


# download code and also transcribes code
def download_audio(link):
    _id = link.strip()  # remove prefix and get video id from youtube vid

    # download youtube video as mp3 file as specified by ydl_opts
    def get_vid(_id):
        with yt_dlp.YoutubeDL(ydl_opts_mp3) as ydl:
            return ydl.extract_info(_id)

    meta = get_vid(
        _id)  #creates yt download object and returns the metadata of the vid
    save_location = meta['id'] + ".mp3"
    duration = meta['duration']
    print('Saved mp3 to', save_location)

    # read audio file
    def read_file(filename):
        with open(filename, 'rb') as _file:
            while True:
                data = _file.read(CHUNK_SIZE)
                if not data:
                    break
                yield data

    # upload audio
    upload_response = requests.post(
        upload_endpoint,
        headers=headers_auth_only,
        data=read_file(
            save_location))  # get the url at which the audio was uploaded to
    audio_url = upload_response.json()['upload_url']
    print('Uploaded to', audio_url)

    # transcribe audio
    transcript_request = {'audio_url': audio_url}
    transcript_response = requests.post(transcript_endpoint,
                                        json=transcript_request,
                                        headers=headers)
    transcript_id = transcript_response.json()['id']
    polling_endpoint = transcript_endpoint + "/" + transcript_id
    print("Transcribing at", polling_endpoint)
    polling_response = requests.get(polling_endpoint, headers=headers)
    while polling_response.json()['status'] != 'completed':
        sleep(30)
        try:
            polling_response = requests.get(polling_endpoint, headers=headers)
        except:
            print("Expected wait time:", duration * 2 / 5, "seconds")
            print("After wait time is up, call poll with id", transcript_id)
            return transcript_id
    _filename = meta['id'] + '.txt'
    with open(_filename, 'w') as f:
        f.write(str(polling_response.json()['words']))
        f.close()
    print('Transcript saved to', _filename)


# download_video(link)
# download_audio(link)

def getTranscript():
    _id = link.strip()
    with open(_id[_id.find('=') + 1:] + '.txt', 'r') as f:
        data = f.read()
        f.close()
        return data

def clip(start, end):
    _id = link.strip()
    video = _id[_id.find('=') + 1:] + '.mp4'
    start_padding = 0.1 if start / 1000 > 0.25 else 0
    return VideoFileClip(video).subclip(start / 1000 - start_padding, end / 1000)

def wordFinder(prompt):
    data = getTranscript()
    transcript = json.loads(data)
    words = {}
    for w in transcript:
        nopunc = re.sub(r"[^a-zA-Z']", '', w['text'])
        if nopunc not in words:
            words[nopunc] = [w['start'], w['end']]
    clips = []
    for word in prompt.split():
        if word in words:
            start = words[word][0]
            end = words[word][1]
            clips.append(clip(start, end))
    final_clip = concatenate_videoclips(clips)
    final_clip.write_videofile("static/final.mp4")
        
wordFinder('make grandma issue little just security')


@app.route('/', methods=['POST', 'GET'])
def home():
    prompt = request.form.get('prompt')
    celebrity = request.form.get('celebrity')
    complete_video = 'static/final.mp4'
    return render_template('index.html', video=complete_video)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=random.randint(2000, 9000))

