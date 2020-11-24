import dill
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

        return

    def open(self):
        """
        """

        # set the acquisition flag
        self.acquiring = True

        # freeze the image shape
        self._width  = self.width
        self._height = self.height

        def f(camera, **kwargs):

            acquiring = kwargs['_acquiring']
            container = kwargs['_container']
            manager   = kwargs['_manager']
            lock      = kwargs['_lock']

            try:
                camera.BeginAcquisition()

                # main acquisition loop
                while acquiring.value:

                    image = camera.GetNextImage()

                    #
                    if not image.IsIncomplete():

                        # convert the image
                        data = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR).GetNDArray().flatten()

                        # store the image (critical - use lock)
                        with lock:
                            container[:] = data

            except:
                return False

        #
        item = (dill.dumps(f), [], {'_acquiring', '_container', '_manager', '_lock'})
        self._iq.put(item)

        return

    def close(self):
        """
        """

        if not self.acquiring:
            return
            
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
        with self._lock:
            image = np.array(self._container[:], dtype=np.uint8).reshape([self._height, self._width])

        return (True, image)
