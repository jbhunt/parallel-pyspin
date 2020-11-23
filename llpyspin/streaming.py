import queue
import logging
import numpy as np
import multiprocessing as mp

# relative imports
from ._processes  import CameraBase
from ._spinnaker  import SpinnakerMixin
from ._properties import PropertiesMixin

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

class VideoStream(CameraBase):
    """
    """

    def __init__(self, device=0):
        """
        """

        super().__init__(device)

        x, y, w, h = self.roi
        self._container = mp.Array('i', w * h)

        return

    def open(self):
        """
        """

        # set the acquisition flag
        self.acquiring = True

        def f(camera):

            try:
                camera.BeginAcquisition()

                # main acquisition loop
                while self.acquiring:

                    try:
                        image = camera.GetNextImage(1)
                    except PySpin.SpinnakerException:
                        continue

                    #
                    if not image.IsIncomplete():

                        # convert the image
                        data = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR).GetNDArray().flatten()

                        # store the image (critical - use lock)
                        with self._container.get_lock():
                            self._container[:] = image
            except:
                return False

            return True

        #
        self._iq.put(dill.dumps(f))

        return

    def close(self):
        """
        """

        self.acquiring = False

        result = self._oq.get()
        if not result:
            logging.log(logging.ERROR, f'acquisition for camera[{self._device}] failed')

        return

    def read(self):
        """
        """

        if not self.acquiring:
            logging.log(logging.INFO, 'stream is closed')
            return (False, None)

        # the lock blocks if a new image is being written to the image attribute
        with self._container.get_lock():
            image = np.array(self._container[:], dtype=np.uint8).reshape([self.height, self.width])

        return (True, image)

    # extend the setter of the roi descriptor
    @CameraBase.roi.setter
    def roi(self, value):

        # invoke the setter
        CameraBase.roi.fset(self, value)

        # recreate the container with the new roi
        x, y, w, h = self.roi
        self._container = mp.Array('i', w * h)

        return
