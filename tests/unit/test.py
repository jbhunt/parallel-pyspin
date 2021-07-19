import os
import numpy as np
import unittest as ut
from llpyspin.primary import PrimaryCamera
from llpyspin.secondary import SecondaryCamera
from llpyspin.streaming import VideoStream
from llpyspin.recording import SpinnakerVideoWriter, OpenCVVideoWriter, FFmpegVideoWriter

class TestVideoWriting(ut.TestCase):
    """
    """

    def setUp(self):
        self.filename = os.path.join(os.environ['HOME'], 'test.mp4')
        self.shape = (100, 100)
        self.framerate = 30
        self.nframes = 3

    def test_spinnaker_backend(self):
        return

    def test_ffmpeg_backend(self):
        return

    def test_opencv_backend(self):
        return

if __name__ == '__main__':
    ut.main()
