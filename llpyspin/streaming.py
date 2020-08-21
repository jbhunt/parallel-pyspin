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

    def _start(self, camera):
        """
        start acquisition
        """

        # engage the acquisition lock
        camera.BeginAcquisition()

        # main acquisition loop
        while self.acquiring:

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

        # TODO : figure out if I really need to check the first condition

        result = True if self._child != None and self.acquiring == True else False

        return result

    def open(self):
        """
        open the stream
        """

        #
        if self.acquiring:
            logging.info('video stream is already open')
            return

        logging.info('opening the video stream')

        # spawn the child process
        self._spawn()

        # initialize the camera
        self._iq.put('initialize')
        if self._result == False:
            logging.debug(f'camera initialization failed')
            self._destroy()

        # set all properties to their default values
        self.framerate = None
        self.exposure  = None
        self.binsize   = None # this will also set the roi

        # set the acquiring flag
        self.acquiring = True

        # start the video acquisition
        self._iq.put('start')

        return

    def release(self):
        """
        """

        if not self.acquiring:
            logging.info('video stream is closed')
            return

        logging.info('releasing the video stream')

        # break out of the acquisition loop
        self.acquiring = False

        # retreive the result (sent after exiting the acquisition loop)
        if self._result == False:
            logging.debug('video acquisition failed')

        # stop acquisition
        self._iq.put('stop')
        if self._result == False:
            logging.debug('video de-acquisition failed')

        # release camera
        self._iq.put('release')
        if self._result == False:
            logging.debug('camera de-initialization failed')

        # kill the child process
        self._kill()

        return

    def read(self):
        """
        get the most recently acquired image
        """

        if not self.acquiring:
            logging.info('stream is closed')
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
