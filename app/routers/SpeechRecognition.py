import speech_recognition_python as sr


#import sys #-- 텍스트 저장시 사용

r = sr.Recognizer()

audio_file = sr.AudioFile('경로.wav')

with audio_file as source:
    audio = r.record(source)


print(r.recognize_google(audio, language='ko-KR'))