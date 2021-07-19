import os
import numpy as np
import unittest as ut
from llpyspin import recording

class TestVideoWriting(ut.TestCase):
    """
    """

    mp4 = os.path.join(os.environ['HOME'], 'test.mp4')
    avi = os.path.join(os.environ['HOME'], 'test.avi')
    shape = (100, 100)
    framerate = 30
    nframes = 3

    def test_spinnaker_backend(self):
        """
        """

        #
        if os.path.exists(self.mp4):
            os.rmdir(self.mp4)

        #
        writer = recording.VideoWriterSpinnaker()
        writer.open(self.mp4, shape=self.shape, framerate=self.framerate)
        for iframe in range(self.nframes):
            image = np.random.randint(low=0, high=255, size=self.shape, dtype=np.uint8)
            writer.write(image)
        writer.close()

        #
        self.assertEqual(os.path.exists(self.mp4), True)

        #
        os.rmdir(self.mp4)

        return

    def test_ffmpeg_backend(self):
        return

    def test_opencv_backend(self):
        return

if __name__ == '__main__':
    ut.main()
