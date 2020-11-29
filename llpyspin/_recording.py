import os
import PySpin
import numpy as np
import subprocess as sp

class VideoWriterSpinnaker(object):
    """
    """

    def __init__(self):
        """
        """

        self._opened = False

        return

    def open(self, filename, shape=(1080, 1440), framerate=30, bitrate=1000000):
        """
        """

        basename, extension = filename.split('.')
        if extension == 'mp4':
            container = PySpin.MJPGOption()
            container.bitrate = bitrate
        elif extension == 'avi':
            container = PySpin.AVIOption()
        else:
            container = PySpin.H264Option()
            container.bitrate = bitrate
            container.height = shape[0]
            container.width = shape[1]
        container.frameRate = framerate

        #
        self._writer = PySpin.SpinVideo()
        self._writer.Open(filename, container)

        #
        self._opened = True

        return

    def write(self, pointer):
        """
        """

        if not self.opened:
            return

        pointer = pointer.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)

        self._writer.Append(pointer)

        return

    def close(self):
        """
        """

        if not self.opened:
            return

        self._writer.Close()

        self._opened = False

        return

    #
    @property
    def opened(self):
        return self._opened

class VideoWriterFFmpeg(object):
    """
    """

    def __init__(self):
        """
        """

        return

    def open(self, filename, shape=(1080, 1440), framerate=30, bitrate=1000000):
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
            '-pix_fmt', 'yuv420p',
            '-i', '-',
            '-filter:v', 'hue=s=0', # this is important - it converts the video to grayscale
            '-an',
            '-crf', '18',
            '-vcodec', 'libx264',
            filename
        ]

        self.p = sp.Popen(command, stdin=sp.PIPE, stdout=sp.DEVNULL, stderr=sp.DEVNULL)

        return self

    def write(self, pointer):
        """
        """

        if not self.running:
            raise sp.SubprocessError('no open process')

        if type(pointer) == np.ndarray:
            image = pointer
        else:
            image = pointer.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR).GetNDArray()

        stacked = np.stack((image,) * 3, axis=-1)

        self.p.stdin.write(stacked.tostring())

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
        return True if hasattr(self, 'p') and self.p.poll() == None else False
