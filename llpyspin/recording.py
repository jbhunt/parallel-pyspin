import os
import PySpin
import skvideo.io

class VideoWriter(object):
    """
    class for creating videos much like OpenCV's VideoWriter class
    """

    def __init__(self, filename, codec='H264', fps=30, shape=None, backend='ffmpeg'):
        """
        """

        try:
            assert codec in [None,'MJPG','H264']
        except AssertionError:
            raise ValueError('invalid codec')

        _params = {
            'bitrate' : 1000000,
            'quality' : 75
        }
        _params.update(kwargs)

        self.filename = filename

        if backend == 'ffmpeg':
            idct = {}
            odct = {'-r' : str(fps), '-c:v' : 'libx264'}
            self.writer = skvideo.io.FFmpegWriter(self.filename, inputdict=idct, outputdict=odct)
            self.write = self._ffmpeg_write
            self.close = self._ffmpeg_close

        elif backend == 'PySpin':
            self.recorder = PySpin.SpinVideo()

            if codec == None:
                self.option = PySpin.AVIOption()

            elif codec == 'MJPG':
                self.option = PySpin.MJPGOption()
                self.option.quality = _params['quality']

            elif codec == 'H264':
                self.option = PySpin.H264Option()
                self.option.bitrate = _params['bitrate']

            #
            self.option.frameRate = fps
            self.recorder.Open(self.filename, self.option)

            #
            self.write = self._pyspin_write
            self.close = self._pyspin_close

        self.open()

        return

    def _ffmpeg_write(self, frame):
        """
        """

        self.writer.writeFrame(frame)

        return

    def _ffmpeg_close(self):
        """
        """

        self.writer.close()

        return

    def _pyspin_write(self, frame):
        """
        save a frame
        """

        self.recorder.Append(frame)

        return

    def _pyspin_close(self):
        """
        close the file
        """

        self.recorder.Close()

        return
