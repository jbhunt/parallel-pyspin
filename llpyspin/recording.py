import os
import PySpin

class VideoWriter(object):
    """
    class for creating videos much like OpenCV's VideoWriter class
    """

    def __init__(self, filename, codec='H264', fps=30, backend='ffmpeg'):
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

            #

            pass

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

        self.open()

        return

    def write(self, frame):
        """
        save a frame
        """

        self.recorder.Append(frame)

        return

    def close(self):
        """
        close the file
        """

        self.recorder.Close()

        return
