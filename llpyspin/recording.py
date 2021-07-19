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

class VideoWriterChildProcess(mp.Process):
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

    def start(self):
        self.started.value = 1
        super().start()

    def join(self, timeout=5):
        self.started.value = 0
        super().join(timeout)

class OpenCVVideoWriterChildProcess(VideoWriterChildProcess):
    """
    """

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

class SpinnakerVideoWriterChildProcess(VideoWriterChildProcess):
    """
    """

    def __init__(self, filename, shape=(1080, 1440), framerate=30, bitrate=1000000):
        super().__init__(filename, shape, framerate)
        self.bitrate = bitrate

    def run(self):
        """
        """

        if self.filename.suffix == '.mp4':
            container = PySpin.MJPGOption()
        elif self.filename.suffix == '.avi':
            container = PySpin.AVIOption()
        else:
            container = PySpin.H264Option()
            container.bitrate = self.bitrate
            container.height = self.height
            container.width = self.width
        container.frameRate = self.framerate

        # initialize the writer
        writer = PySpin.SpinVideo()
        writer.Open(str(self.filename), container)

        while self.started.value:
            try:
                image = self.q.get(timeout=False)
                pointer = PySpin.Image_Create(self.width, self.height, 0, 0, PySpin.PixelFormat_Mono8, image)
                writer.Append(pointer)
            except queue.Empty:
                continue

        writer.Close()

        return

class FFmpegVideoWriterChildProcess(VideoWriterChildProcess):

    def run(self):
        args = (
            'ffmpeg',
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{self.width}x{self.height}',
            '-r', f'{self.framerate}',
            '-pix_fmt', 'rgb24',
            '-i', '-',
            '-preset', 'veryslow',
            '-pix_fmt', 'yuv420p',
            '-filter:v', 'hue=s=0', # this is important - it converts the video to grayscale
            '-an',
            '-crf', '0',
            '-vcodec', 'libx264',
            str(self.filename)
        )
        command = ' '.join(args)

        p = sp.Popen(command, stdin=sp.PIPE, stdout=sp.DEVNULL, stderr=sp.DEVNULL, shell=True)

        while self.started.value:
            try:
                image = self.q.get(timeout=False)
                if len(image.shape) != 3:
                    image = np.stack((image,) * 3, axis=-1)
                p.stdin.write(image)
            except queue.Empty:
                continue

        p.stdin.close()
        p.wait()

        return

class VideoWriter():
    """
    """

    def __init__(self):
        self.p = None

    def open(self, filename):
        if self.p is not None:
            raise VideoWritingError('Video writer is already open')

        self.filename = pl.Path(filename)

        # create the parent directory if necessary
        if not self.filename.parent.exists():
            self.filename.parent.mkdir()

        # convert the file name to an absolute file path
        if not self.filename.is_absolute():
            self.filename = self.filename.absolute()

    def close(self):
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
        if self.p is None:
            raise VideoWritingError('Video writer is closed')
        else:
            if isinstance(pointer, np.ndarray):
                self.p.q.put(pointer)
            elif isinstance(pointer, PySpin.ImagePtr):
                self.p.q.put(pointer.GetNDArray())
            else:
                raise VideoWritingError(f'Cannot write object of type {type(pointer)} to video file')

class OpenCVVideoWriter(VideoWriter):
    """
    """

    def __init__(self):
        """
        """

        super().__init__()

        # Raise an error if OpenCV is not installed
        global OPENCV_IMPORT_RESULT
        if OPENCV_IMPORT_RESULT == False:
            raise VideoWritingError('OpenCV import failed')

        return

    def open(self, filename, shape=(1080, 1440), framerate=30, bitrate=None):
        """
        """

        super().open(filename)

        kwargs = {
            'filename': self.filename,
            'shape': shape,
            'framerate': framerate,
        }
        self.p = OpenCVVideoWriterChildProcess(**kwargs)
        self.p.start()

        return

class SpinnakerVideoWriter(VideoWriter):
    """
    """

    def __init__(self):
        """
        """

        super().__init__()

        return

    def open(self, filename, shape=(1080, 1440), framerate=30, bitrate=1000000):
        """
        """

        super().open(filename)

        kwargs = {
            'filename': self.filename,
            'shape': shape,
            'framerate': framerate,
            'bitrate': bitrate
        }
        self.p = SpinnakerVideoWriterChildProcess(**kwargs)
        self.p.start()

        return

    def close(self):
        super().close()
        actual = f'{str(self.filename.name)}-0000.avi'
        src = str(self.filename.parent / pl.Path(actual))
        os.rename(src, str(self.filename))


class FFmpegVideoWriter(VideoWriter):
    """
    """

    def __init__(self, print_ffmpeg_path=False):
        """
        """

        super().__init__()

        # check if ffmpeg is installed
        if sys.platform == "linux" or platform == "linux2":
            p = sp.Popen('which ffmpeg', stdout=sp.PIPE, shell=True)
        elif sys.platform == "win32":
            p = sp.Popen('where ffmpeg', stdout=sp.PIPE, shell=True)
        else:
            raise VideoWritingError('Only Windows and Linux operating systems are supported')

        out, err = p.communicate()
        if p.returncode == 1:
            raise VideoWritingError('FFmpeg not installed (or binary not locatable)')
        if p.returncode == 0 and print_ffmpeg_path:
            print(f'FFmpeg executable found at {out.decode()}')

        return

    def open(self, filename, shape=(1080, 1440), framerate=30, bitrate=None):
        """
        """

        super().open(filename)

        kwargs = {
            'filename': self.filename,
            'shape': shape,
            'framerate': framerate,
        }
        self.p = FFmpegVideoWriterChildProcess(**kwargs)
        self.p.start()
