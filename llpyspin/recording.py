import os
import sys
import PySpin
import numpy as np
import pathlib as pl
import subprocess as sp

class VideoWritingError(Exception):
    def __init__(self, message):
        super().__init__(message)

class VideoWriterSpinnaker():
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

        # make the destination directory if necessary
        path = pl.Path(filename)
        if not path.parent.exists():
            os.mkdir(str(path.parent))

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

    def __init__(self, print_ffmpeg_path=False):
        """
        """

        # check if ffmpeg is installed
        if sys.platform == "linux" or platform == "linux2":
            p = sp.Popen('which ffmpeg', stdout=sp.PIPE, shell=True)
        elif sys.platform == "win32":
            p = sp.Popen('Where-Object ffmpeg', stdout=sp.PIPE, shell=True)
        else:
            raise VideoWritingError('Only Windows and Linux operating systems are supported')

        out, err = p.communicate()
        if p.returncode == 1:
            raise VideoWritingError('FFmpeg not installed')
        if p.returncode == 0 and print_ffmpeg_path:
            print(f'FFmpeg executable found at {out.decode()}')

        return

    def open(self, filename, shape=(1080, 1440), framerate=30, bitrate=1000000):
        """
        """

        if self.running:
            raise sp.SubprocessError('an open process is still running')

        # make the destination directory if necessary
        path = pl.Path(filename)
        if not path.parent.exists():
            os.mkdir(str(path.parent))

        # command definition
        elements = [
            'ffmpeg',
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{shape[1]}x{shape[0]}',
            '-r', f'{framerate}',
            '-pix_fmt', 'rgb24',
            '-i', '-',
            '-preset', 'veryslow',
            '-pix_fmt', 'yuv420p',
            '-filter:v', 'hue=s=0', # this is important - it converts the video to grayscale
            '-an',
            '-crf', '0',
            '-vcodec', 'libx264',
            filename
        ]
        command = ' '.join(elements)

        self.p = sp.Popen(command, stdin=sp.PIPE, stdout=sp.DEVNULL, stderr=sp.DEVNULL, shell=True)

        return self

    def write(self, pointer):
        """
        """

        if not self.running:
            raise sp.SubprocessError('no open process')

        if type(pointer) == np.ndarray:
            image = pointer
        else:
            image = pointer.GetNDArray()

        # duplicate the array along a third axis
        if len(image.shape) != 3:
            image = np.stack((image,) * 3, axis=-1)

        self.p.stdin.write(image)

        return

    def close(self):
        """
        """

        if not self.running:
            raise sp.SubprocessError('No open process')

        self.p.stdin.close()
        self.p.wait()

        return

    # this flag monitors the state of the child process
    @property
    def running(self):
        return True if hasattr(self, 'p') and self.p.poll() == None else False
