import queue
import logging
import numpy as np
import multiprocessing as mp

# relative imports
from ._processes  import CameraBase
from ._spinnaker  import SpinnakerMixin, spinnaker
from ._properties import PropertiesMixin
from ._constants  import *

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

class VideoStream(CameraBase, SpinnakerMixin, PropertiesMixin):
    """
    a class for streaming video, i.e., where recording is not the target function
    """

    def __init__(self, device=0):
        """
        """

        super().__init__(device)

        # this bit of memory stores the image
        self._container = mp.Array('i',3000000)

        # open the stream
        self.open()

        return

    @spinnaker
    def _start(self, camera):
        """
        start acquisition
        """

        # engage the acquisition lock
        camera.BeginAcquisition()

        # main acquisition loop
        while self._acquiring.value:

            image = camera.GetNextImage(1000)

            #
            if not image.IsIncomplete():

                # convert the image
                frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
                array = frame.GetNDArray().flatten()
                image = np.zeros_like(self._container[:])
                image[:array.size] = array

                # store the image (critical - use lock)
                with self._container.get_lock():
                    self._container[:] = image

        return

    ### public methods ###

    def isOpened(self):
        """
        """

        result = True if self.child is not None and self.acquiring is True else False

        return result

    def open(self):
        """
        open the stream
        """

        # assert that the stream is closed
        try:
            assert self.isOpened() == False
        except AssertionError:
            logging.info('The video stream is already open.')
            return

        logging.info('Opening the video stream.')

        # initialize the child process
        self._create()

        # attempt to initialize the camera
        self._iq.put(INITIALIZE)
        result = self._oq.get()
        if not result:
            logging.debug(f'camera initialization failed')
            self._destroy()

        # set all properties to their default values
        self._setall()

        # set the acquiring flag
        self.acquiring = True

        # start the video acquisition
        self._iq.put(START)

        return

    def release(self):
        """
        """

        if self.isOpened() == False:
            logging.info("The video stream is closed,")
            return

        logging.info('Releasing the video stream.')

        # break out of the acquisition loop
        self.acquiring = False

        # retreive the result (sent after exiting the acquisition loop)
        result = self._oq.get()
        if not result:
            logging.debug('video acquisition failed')

        # stop acquisition
        self._iq.put(STOP)
        result = self._oq.get()
        if not result:
            logging.debug('video de-acquisition failed')

        # release camera
        self._iq.put(RELEASE)
        result = self._oq.get()
        if not result:
            logging.debug('camera de-initialization failed')

        # destroy the child process
        self._destroy()

        return

    def read(self):
        """
        get the most recently acquired image
        """

        # check that the stream is open
        if self.isOpened() == False:
            logging.info('The stream is closed.')
            return (False, None)

        # the lock blocks if a new image is being written to the image attribute
        with self._container.get_lock():
            array = np.array(self._container[:],dtype=np.uint8)
            index = np.arange(self.size,array.size)
            if len(index) != 0:
                array = np.delete(array, index)
            image = array.reshape((self.height,self.width))

        return (True, image)

    @property
    def size(self):
        (i, j, h, w) = self.roi
        return w * h

    @property
    def height(self):
        (i, j, h, w) = self.roi
        return h

    @property
    def width(self):
        (i, j, h, w) = self.roi
        return w
