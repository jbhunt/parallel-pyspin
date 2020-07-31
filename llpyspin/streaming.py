from llpyspin import constants
from llpyspin import capture

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

class VideoStream(capture.VideoCaptureBase):
    """
    """

    def __init__(self, device=0):
        """
        """

        super().__init__(device)

        # public attributes
        self.image = None
        self.shape = None

        # open the stream
        self.open()

        return

    ### special methods ###

    def _start(self, camera):
        """
        start acquisition
        """

        try:
            #
            camera.BeginAcquisition()

            # grab the properties of the image using a sample image
            sample = camera.GetNextImage()

            # retreive the image shape
            width  = sample.GetWidth()
            height = sample.GetHeight()
            depth  = sample.GetNumChannels() # not in use now because all images are Mono8

            # store the image shape - I'm not sure if this needs to be proces-safe but it couldn't hurt
            self.shape = mp.Array('i',3)
            self.shape[:] = np.array([height,width,depth])

            # create an array object for the image
            self.image = mp.Array('i',width * height)

            # main loop
            while self.acquiring.value:

                image = camera.GetNextImage()

                #
                if not image.IsIncomplete():

                    # convert the image
                    frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)

                    # store the image (critical - use lock)
                    with self.image.get_lock():
                        self.image[:] = frame.GetNDArray().flatten()

                image.Release()

            result = constants.SUCCESS

        except PySpin.SpinnakerException:
            result = constants.FAILURE

        return

    def _stop(self, camera):
        """
        stop acquisition
        """

        try:

            # stop acquisition
            if camera.IsStreaming():
                camera.EndAcquisition()

            result = constants.SUCCESS

        except PySpin.SpinnakerException:
            result = constants.FAILURE

        return

    ### public methods ###

    def isOpened(self):
        """
        """

        result = True if self.child is not None and self.acquiring else False

        return result

    def open(self):
        """
        open the stream
        """

        # assert that the stream is closed
        try:
            assert not self.isOpened()
        except AssertionError:
            logging.info('The video stream is already open.')
            return

        logging.info('Opening the video stream.')

        # initialize the child process
        self._initializeChild()

        # initialize the camera
        attempt   = 0 # attempt counter
        threshold = 5 # max number of attempts allowed
        result    = constants.FAILURE # default result

        while not result:

            # check attempt counter
            attempt += 1
            if attempt > threshold:
                logging.error(f'Failed to initialize the camera with {attempt} attempts. Destroying child.')
                self._destroyChild()
                return

            # attempt to initialize the camera
            self._.iq.put(constants.INITIALIZE)
            result = self._.oq.get()

            # restart the child process
            if not result:
                logging.warning(f'Camera initialization failed (attempt number {attempt}). Restarting child.')
                self._destroyChild()
                self._initializeChild()
                continue

        # set all properties to their default values
        self._setAllProperties()

        # set the acquiring flag
        self.acquiring = 1

        # start the video acquisition
        self._child.iq.put(constants.START)

        return

    def release(self):
        """
        """

        try:
            assert self.isOpened()
        except AssertionError:
            logging.info("The video stream is closed. Call the 'open' method")
            return

        logging.info('Releasing the video stream.')

        # break out of the acquisition loop
        self.acquiring = 0

        # retreive the result (sent after exiting the acquisition loop)
        result = self._.oq.get()
        if not result:
            logging.warning('Video acquisition failed.')

        # stop acquisition
        self._.iq.put(constants.STOP)
        result = self._.oq.get()
        if not result:
            logging.warning('Video de-acquisition failed.')

        # release camera
        self._.iq.put(constants.RELEASE)
        result = self._.oq.get()
        if not result:
            logging.warning('Camera de-initialization failed.')

        # destroy the child process
        self._destroyChild()

        return

    def read(self):
        """
        get the most recently acquired image
        """

        try:

            # check that the stream is open
            assert self.isOpened() is True

            # retreive image shape - this will raise a TypeError if the shape attribute is undefined
            (height, width, depth) = self.shape[:]

            # the lock blocks if a new image is being written to the image attribute
            with self.image.get_lock():

                # transform the raw data into a correctly shaped numpy array
                image = np.array(self.image[:],dtype=np.uint8).reshape((height,width))

            result = True

        except AssertionError:
            logging.warning('The stream is closed.')
            image  = None
            result = False

        except TypeError:
            logging.warning('The image shape is undefined.')
            image = None
            result = False

        return (result,image)
