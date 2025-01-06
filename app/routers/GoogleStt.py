from google.cloud import speech  # 구글 클라우드의 speech(음성 인식) API를 사용하기 위한 라이브러리를 임포트


def transcribe_gcs(gcs_uri: str) -> str:
    """이 함수는 구글 클라우드 스토리지에 있는 오디오 파일을 텍스트로 변환합니다.

    Args:
        gcs_uri: 구글 클라우드 스토리지에 있는 오디오 파일의 경로.
            예시: "gs://storage-bucket/file.flac" (여기서 gs://은 클라우드 저장소 위치를 나타냄)

    Returns:
        텍스트로 변환된 오디오의 내용을 반환.
    """

    # 구글 클라우드 음성 인식 API 클라이언트를 생성
    client = speech.SpeechClient()

    # 클라우드 스토리지에 있는 오디오 파일을 읽기 위한 설정
    audio = speech.RecognitionAudio(uri="gs://speak-to-text-test/")

    # 오디오 파일을 어떻게 처리할지에 대한 설정 (파일 형식, 샘플링 주파수, 언어 코드 등)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.FLAC,  # 오디오 파일 형식
        sample_rate_hertz=44100,  # 샘플링 주파수 (초당 샘플의 수)
        language_code="ko-KR",  # 사용할 언어 (한국어)
    )

    # 오디오를 분석하기 위해 구글 API에게 작업을 요청
    operation = client.long_running_recognize(config=config, audio=audio)

    # 결과가 나올 때까지 기다리고 결과를 받아옵니다.
    print("Waiting for operation to complete...")
    response = operation.result(timeout=90)  # 최대 90초까지 기다림

    # 결과를 저장할 빈 리스트를 생성
    transcript_builder = []

    # 오디오 파일이 여러 부분으로 나뉘어 있을 수 있기 때문에 각 부분의 결과를 하나씩 처리
    for result in response.results:
        # 각 부분에서 가장 가능성 높은 텍스트를 뽑아서 transcript_builder에 추가
        transcript_builder.append(f"\nTranscript: {result.alternatives[0].transcript}")
        transcript_builder.append(f"\nConfidence: {result.alternatives[0].confidence}")

    # transcript_builder에 저장된 텍스트들을 하나의 문자열로 합침
    transcript = "".join(transcript_builder)

    # 결과를 출력해서 확인
    print(transcript)

    # 최종적으로 텍스트로 변환된 내용을 반환
    return transcript
