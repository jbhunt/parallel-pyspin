import dill
import queue
import PySpin
import logging
import numpy as np
import multiprocessing as mp

# relative imports
from ._processes  import MainProcess

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

class VideoStream(MainProcess):
    """
    """

    def __init__(self, device=0):
        """
        """

        super().__init__(device)

        self._initialize()

        return

    def open(self):
        """
        """

        # initialize the camera if needed
        if not self._child.started:
            self._initialize()

        # set the acquisition flag
        self.acquiring = True

        def f(camera, *args, **kwargs):

            # unpack the kwargs
            shape     = kwargs['shape']
            acquiring = kwargs['acquiring']

            # size of the image (i.e., total number of pixels)
            size = shape[0] * shape[1]

            try:
                camera.BeginAcquisition()

                # main acquisition loop
                while acquiring.value:

                    try:
                        image = camera.GetNextImage(1)
                    except PySpin.SpinnakerException:
                        continue

                    #
                    if not image.IsIncomplete():

                        # convert the image
                        data = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR).GetNDArray().flatten()

                        # store the image (critical - use lock)
                        with buffer.get_lock():
                            buffer[:size] = data

                return True

            except:
                return False

        # pack the kwargs
        kwargs = {
            'shape'     : (self.height, self.width),
            'acquiring' : self._acquiring
        }
        item = (dill.dumps(f), [], kwargs)
        self._child.iq.put(item)

        return

    def close(self):
        """
        """

        if not self.acquiring:
            return

        self.acquiring = False

        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'acquisition for camera[{self._device}] failed')

        def f(camera, *args, **kwargs):
            try:
                camera.EndAcquisition()
                return True
            except:
                return False

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'video deacquisition for camera[{self._device}] failed')

        # release the camera
        self._release()

        return

    def read(self):
        """
        """

        if not self.acquiring:
            logging.log(logging.INFO, 'stream is closed')
            return (False, None)

        # the lock blocks if a new image is being written to the image attribute
        # with self._buffer_lock:
        with self._child.buffer.get_lock():
            data = self._child.buffer[:][:self.width * self.height]
            image = np.array(data, dtype=np.uint8).reshape([self.height, self.width])

        return (True, image)
