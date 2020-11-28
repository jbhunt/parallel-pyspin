import os
import queue
import PySpin
import numpy as np
import subprocess as sp
import multiprocessing as mp

def f(started, q, params):
    """
    target function for the VideoWriterPySpin class
    """

    # select the appropriate codec
    head, tail = params['filename'].split('.')
    if tail == 'mp4':
        option = PySpin.MJPGOption()
        option.bitrate = params['bitrate']
    elif tail == 'avi':
        option = PySpin.AVIOption()
    else:
        option = PySpin.H264Option()
        option.bitrate = params['bitrate']
        option.height  = params['shape'][1]
        option.width   = params['shape'][0]

    option.frameRate = params['framerate']
    recorder = PySpin.SpinVideo()
    recorder.Open(params['filename'], option)

    while started.value:

        #
        try:
            result = q.get(block=False)
        except queue.Empty:
            continue

        #
        recorder.Append(result)
        result.Release()

    #
    recorder.Close()

    return

# doesn't work
class VideoWriterPySpin():
    """
    """

    def __init__(self):
        """
        """

        self.q = mp.Queue()
        self.started = mp.Value('i', 0)

        return

    def open(self, filename, framerate=30, bitrate=1000000):
        """
        """

        if self.running:
            return

        params = {
            'framerate' : framerate,
            'filename'  : filename,
            'bitrate'   : bitrate
        }

        self.p = mp.Process(target=f, args=(self.started, self.q, params))
        self.started.value = 1
        self.p.start()

        return self

    def write(self, result):
        """
        """

        if not self.running:
            return

        self.q.put(result)

        return

    def close(self):
        """
        """

        if not self.running:
            return

        while self.q.qsize() != 0:
            continue
        self.started.value = 0
        self.p.join()

        return

    @property
    def running(self):
        return True if hasattr(self, 'p') and self.p.is_alive() else False



class VideoWriterFFmpeg(object):
    """
    """

    def __init__(self):
        """
        """

        return

    def open(self, filename, shape=(1080,1440), framerate=30, bitrate=1000000):
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
            '-pix_fmt', 'rgb24',
            '-i', '-',
            '-filter:v', 'hue=s=0', # this is important - it converts the video to grayscale
            '-an',
            '-vcodec', 'libx265',
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

        rgb = np.stack((gray,) * 3, axis=-1)

        self.p.stdin.write(rgb.tostring())

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
