import os
import queue
import PySpin
import numpy as np
import subprocess as sp
import multiprocessing as mp

def f(started, q, **params):
    """
    target function for the VideoWriterPySpin class
    """

    option = PySpin.H264Option()
    option.bitrate = params['bitrate']
    option.frameRate = params['framerate']
    recorder = PySpin.SpinVideo()
    recorder.Open(filename, option)

    while started.value:

        #
        try:
            result = q.get(block=False)
        except queue.Empty:
            continue

        #
        image = result.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR).GetNDArray()
        recorder.write(image)
        result.Release()

    return

class VideoWriterPySpin():
    """
    """

    def __init__(self):
        """
        """

        self.q = mp.Queue()
        self.started = mp.Value('i', 1)

        return

    def open(self, filename, framerate=30, bitrate=1000000):
        """
        """

        if self.p.is_alive():
            return

        params = {
            'framerate' : framerate,
            'bitrate'   : bitrate
        }

        self.p = mp.Process(target=f, args=(self.started, self.q, params))
        self.p.start()

        return self

    def write(self, result):
        """
        """

        if not self.p.is_alive():
            return

        self.q.put(result)

        return

    def close(self):
        """
        """

        if not self.p.is_alive():
            return

        while self.q.qsize() != 0:
            continue
        self.started.value = 0
        self.p.join()

        return

class VideoWriterFFmpeg(object):
    """
    """

    def __init__(self):
        """
        """

        return

    def open(self, filename, shape=(540,720), framerate=30):
        """
        """

        if self.running:
            raise sp.SubprocessError('an open process is still running')

        # command definition
        command = [
            'ffmpeg',
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{shape[1]}x{shape[0]}',
            '-r', f'{framerate}',
            '-i', '-',
            '-filter:v', 'hue=s=0', # this is important - it converts the video to grayscale
            '-an',
            '-vcodec', 'libx264',
            filename
        ]

        self.p = sp.Popen(command, stdin=sp.PIPE, stdout=sp.DEVNULL, stderr=sp.DEVNULL)

        return self

    def write(self, result):
        """
        """

        if not self.running:
            raise sp.SubprocessError('no open process')

        if type(result) == np.ndarray:
            gray = result
        else:
            gray = result.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR).GetNDArray()
            result.Release()

        data = np.stack((gray,) * 3, axis=-1).tostring()
        self.p.stdin.write(data)

        return

    def close(self):
        """
        """

        if not self.running:
            raise sp.SubprocessError('no open process')

        self.p.stdin.close()
        self.p.wait()

        return

    # this flag monitors the state of the child process
    @property
    def running(self):
        try:
            assert hasattr(self, 'p')
        except AssertionError:
            return False
        return True if self.p.poll() == None else False
