from llpyspin._construct import ChildProcessMixin
from llpyspin._construct import SpinnakerMethodsMixin
from llpyspin._construct import AcquisitionPropertiesMixin
from llpyspin._construct import VideoCameraBase
from llpyspin._construct import SpinnakerMethod

from llpyspin import constants

import queue
import logging
import numpy as np
import multiprocessing as mp

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

# list of mixins
mixins = [ChildProcessMixin,SpinnakerMethodsMixin,AcquisitionPropertiesMixin]

class VideoStream(VideoCameraBase,*mixins):
    """
    a class for streaming video, i.e., where recording is not the target function
    """

    def __init__(self, device=0):
        """
        """

        super().__init__(device)

        # public attributes
        self._current   = np.zeros([1440,1080])
        self._previous  = np.zeros([1440,1080])
        self._retreived = mp.Array('i',1080 * 1440)

        # open the stream
        self.open()

        return

    @SpinnakerMethod
    def _start(self, camera):
        """
        start acquisition
        """

        camera.BeginAcquisition()

        # main loop
        while self._acquiring.value:

            image = camera.GetNextImage()

            #
            if not image.IsIncomplete():

                # convert the image
                frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)

                # store the image (critical - use lock)
                with self._retreived.get_lock():
                    self._retreived[:] = frame.GetNDArray().flatten()

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

        # initialize the camera
        attempt   = 0 # attempt counter
        threshold = 5 # max number of attempts allowed
        result    = False # default result

        while not result:

            # check attempt counter
            attempt += 1
            if attempt > threshold:
                logging.error(f'Failed to initialize the camera with {attempt} attempts. Destroying child.')
                self._destroys()
                return

            # attempt to initialize the camera
            self._iq.put(constants.INITIALIZE)
            result = self._oq.get()

            # restart the child process
            if not result:
                logging.debug(f'Camera initialization failed (attempt number {attempt}). Restarting child.')
                self._destroy()
                self._create()
                continue

        # set all properties to their default values
        self._setall()

        # set the acquiring flag
        self.acquiring = True

        # start the video acquisition
        self._iq.put(constants.START)

        return

    def release(self):
        """
        """

        try:
            assert self.isOpened() == True
        except AssertionError:
            logging.info("The video stream is closed,")
            return

        logging.info('Releasing the video stream.')

        # break out of the acquisition loop
        self.acquiring = False

        # retreive the result (sent after exiting the acquisition loop)
        result = self._oq.get()
        if not result:
            logging.debug('Video acquisition failed.')

        # stop acquisition
        self._iq.put(constants.STOP)
        result = self._oq.get()
        if not result:
            logging.debug('Video de-acquisition failed.')

        # release camera
        self._iq.put(constants.RELEASE)
        result = self._oq.get()
        if not result:
            logging.debug('Camera de-initialization failed.')

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
            return (None, False)

        # the lock blocks if a new image is being written to the image attribute
        with self._retreived.get_lock():

            # transform the raw data into a correctly shaped numpy array
            self._current = np.array(self._retreived[:],dtype=np.uint8).reshape((1080,1440))

        try:
            assert np.array_equal(self._previous,self._current) == False

        except AssertionError:
            logging.debug('The same image was retreived twice.')
            return (True, self._current)

        self._previous = self._current

        return (True,self._current)
