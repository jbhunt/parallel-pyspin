import os
import sys
import queue
import PySpin
import numpy as np
import pathlib as pl
import subprocess as sp
import multiprocessing as mp

# try to import OpenCV
try:
    import cv2 as cv
    OPENCV_IMPORT_RESULT = True
except ModuleNotFoundError:
    OPENCV_IMPORT_RESULT = False

class VideoWritingError(Exception):
    def __init__(self, message):
        super().__init__(message)

class VideoWriterOpenCVChildProcess(mp.Process):
    """
    """

    def __init__(self, filename, shape=(1080, 1440), framerate=30):
        """
        """

        super().__init__()

        # absolute file path to the movie
        self.filename = filename

        # multiprocessing queue for image transfer
        self.q = mp.Queue()

        # started flag
        self.started = mp.Value('i', 0)

        # video parameters
        self.height, self.width = shape
        self.framerate = framerate

        return

    def run(self):
        """
        """

        # select the appropriate codec
        if self.filename.suffix == '.mp4':
            codec = 'mp4v'
        elif self.filename.suffix == '.avi':
            codec = 'MJPG'
        else:
            codec = 'H264'

        # create the video writer object
        fourcc = cv.VideoWriter_fourcc(*codec)
        writer = cv.VideoWriter(
            str(self.filename),
            fourcc,
            self.framerate,
            (self.width, self.height),
            False
        )

        # main loop
        while self.started.value:
            try:
                image = self.q.get(block=False)
                writer.write(image)
            except queue.Empty:
                continue

        # close the writer object
        writer.release()

        return

    def start(self):
        """
        """

        # set the started flag to True
        self.started.value = 1

        super().start()

        return

    def join(self, timeout=5):
        """
        """

        # break out of the main loop in the run method
        self.started.value = 0

        super().join(timeout)

        return

class VideoWriterOpenCV():
    """
    """

    def __init__(self):
        """
        """

        # Raise an error if OpenCV is not installed
        global OPENCV_IMPORT_RESULT
        if OPENCV_IMPORT_RESULT == False:
            raise VideoWritingError('OpenCV import failed')

        self.p = None

        return

    def open(self, filename, shape=(1080, 1440), framerate=30, bitrate=None):
        """
        """

        if self.p is not None:
            raise VideoWritingError('Video writer is already open')

        path = pl.Path(filename)

        # create the parent directory if necessary
        if not path.parent.exists():
            path.parent.mkdir()

        # convert the file name to an absolute file path
        if not path.is_absolute():
            path = path.absolute()

        kwargs = {
            'filename': path,
            'shape': shape,
            'framerate': framerate,
        }
        self.p = VideoWriterOpenCVChildProcess(**kwargs)
        self.p.start()

        return

    def close(self):
        """
        """

        if self.p is None:
            raise VideoWritingError('Video writer is already closed')
        else:
            try:
                self.p.join(5)
                self.p = None
            except mp.TimeoutError:
                self.p.terminate()
                self.p.join()
                self.p = None
                raise VideoWritingError('Child process was terminated after hanging')

        return

    def write(self, pointer):
        """
        """

        if self.p is None:
            raise VideoWritingError('Video writer is closed')
        else:
            if isinstance(pointer, np.ndarray):
                self.p.q.put(pointer)
            elif isinstance(pointer, PySpin.ImagePtr):
                self.p.q.put(pointer.GetNDArray())
            else:
                raise VideoWritingError(f'Cannot write object of type {type(pointer)} to video file')

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
            p = sp.Popen('where ffmpeg', stdout=sp.PIPE, shell=True)
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
