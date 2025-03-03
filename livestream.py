import av
import streamlink

def get_container(url):
    """
    Open the HLS stream using streamlink and PyAV,
    and return the container.
    """
    streams = streamlink.streams(url)
    if "best" not in streams:
        raise Exception("No suitable stream found.")
    stream_obj = streams["best"]
    raw_stream = stream_obj.open()

    class StreamWrapper:
        def read(self, size=-1):
            return raw_stream.read(size)
        def readable(self):
            return True

    wrapped = StreamWrapper()
    container = av.open(wrapped)
    return container

def frame_generator(container):
    """
    Generator that yields decoded video frames as BGR images.
    """
    for frame in container.decode(video=0):
        yield frame.to_ndarray(format='bgr24')
