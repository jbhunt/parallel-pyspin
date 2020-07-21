# imports
import logging
import numpy as np

# image properties
from .constants import IMAGE_SIZE, IMAGE_SHAPE, IMAGE_WIDTH, IMAGE_HEIGHT

# default acquisition property key and value pairs
from .constants import CAP_PROP_FPS, CAP_PROP_FPS_DEFAULT
from .constants import CAP_PROP_BINSIZE, CAP_PROP_BINSIZE_DEFAULT
from .constants import CAP_PROP_EXPOSURE, CAP_PROP_EXPOSURE_DEFAULT

#
from .children import VideoStreamChildProcess

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

class VideoStream():
    """
    OpenCV-like video stream for a single BlackflyS camera

    notes
    -----
    This object operates like OpenCV's VideoCapture class
    """

    def __init__(self, device=0):
        """
        keywords
        --------
        device : int
            device index which specifies the camera
        """

        # init and start the process
        self.device = device

        # start the child process
        self._startChild()

        # set the default capture properties
        self._framerate = CAP_PROP_FPS_DEFAULT
        self._binsize   = CAP_PROP_BINSIZE_DEFAULT
        self._exposure  = CAP_PROP_EXPOSURE_DEFAULT

        # start acquisition
        self.open()

        return

    def _startChild(self):
        """
        start the child process
        """

        self._child = VideoStreamChildProcess(self.device)
        self._child.start()

        return

    def open(self):
        """
        open the stream
        """

        # assert that the stream is closed
        try:
            assert self.isOpened() is False
        except AssertionError:
            logging.info('Video stream is already open.')
            return

        # check that the child process is alive
        try:
            assert self._child.is_alive()
        except AssertionError:
            self._startChild()

        # initialize the camera
        self._child.iq.put('initialize')
        result = self._child.oq.get()
        if not result:
            logging.error('Camera initialization failed.')
            return

        values = [self._framerate,self._binsize,self._exposure]
        properties = [CAP_PROP_FPS,CAP_PROP_BINSIZE,CAP_PROP_EXPOSURE]

        for (property,value) in zip(properties,values):
            self._child.iq.put('set')
            self._child.iq.put(property)
            self._child.iq.put(value)
            result = self._child.oq.get()

            if not result:
                logging.warning(f'Failed to set {property} to {value}.')

        self._child.iq.put('acquire')

        return

    def set(self, property, value):
        """
        set the value of a valid acquisition property
        """

        # check that the requested property is valid
        try:
            assert hasattr(self,f'_{property}')

        except AssertionError:
            logging.warning(f'{property} is not a supported property.')
            return

        # set the new property value
        self.__setattr__(f'_{property}',value)

        # release the stream if open
        if self.isOpened():
            self.release()

        # (re-)open the stream
        self.open()

        return

    def get(self, property):
        """
        return the value of a valid capture property
        """

        try:
            assert hasattr(self,f'_{property}')
        except AssertionError:
            logging.warning(f'{property} is not a valid property')

        return self.__getattribute__(f'_{property}')

    def isOpened(self):
        """
        returns
        -------
        result : bool
            True if streaming else False
        """

        result = True if self._child.acquiring.value == 1 else False

        return result

    def read(self):
        """
        grab the most recently acquired image
        """

        result = True

        try:

            # the lock blocks if a new image is being acquired / stored in the image attribute
            with self._child.image.get_lock():
                image = np.array(self._child.image[:],dtype=np.uint8).reshape(IMAGE_SHAPE)

        except:
            image = None
            result = False

        return (result,image)

    def release(self):
        """
        release the video stream
        """

        try:
            assert self.isOpened() is True

        except AssertionError:
            logging.info('Video stream is already stopped.')
            return

        # break out of the acquisition loop
        self._child.acquiring.value = 0

        # retreive the result (sent after exiting the acquisition loop)
        result = self._child.oq.get()
        if not result:
            logging.warning('Video acquisition failed.')

        # stop acquisition
        self._child.iq.put('deacquire')
        result = self._child.oq.get()
        if not result:
            logging.warning('Video de-acquisition failed.')

        # de-init the camera
        self._child.iq.put('deinitialize')
        result = self._child.oq.get()
        if not result:
            logging.warning('Camera de-initialization failed.')

        # break out of the main loop
        self._child.started.value = 0
        self._child.join()

        return
