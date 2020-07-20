# imports
import logging

# image properties
from .constants import IMAGE_SIZE, IMAGE_SHAPE, IMAGE_WIDTH, IMAGE_HEIGHT

# default acquisition property key and value pairs
from .constants import CAP_PROP_FPS, CAP_PROP_FPS_DEFAULT
from .constants import CAP_PROP_BINSIZE, CAP_PROP_BINSIZE_DEFAULT
from .constants import CAP_PROP_EXPOSURE, CAP_PROP_EXPOSURE_DEFAULT

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
        self._child = VideoStreamChildProcess(device)
        self._child.start()

        # initialize the camera
        self._child.iq.put('initialize')
        result = self._child.oq.get()

        # read out the result
        if not result:
            logging.error('Camera initialization failed.')
            return

        # set the default acquisition property values
        properties = [
            CAP_PROP_FPS,
            CAP_PROP_BINSIZE,
            CAP_PROP_EXPOSURE
            ]

        values = [
            CAP_PROP_FPS_DEFAULT,
            CAP_PROP_BINSIZE_DEFAULT,
            CAP_PROP_EXPOSURE_DEFAULT
            ]

        for (property,value) in zip(properties,values):
            self._child.iq.put('set')
            self._child.iq.put(property)
            self._child.iq.put(value)
            result = self._child.oq.get()

            if not result:
                logging.warning(f'Failed to set {property} to {value}.')

        # start acquisition
        self._start()

        return

    def _start(self):
        """
        start video acquisition
        """

        # check that the camera isn't acquiring
        try:
            assert self._child.acquiring.value == 0
        except AssertionError:
            logging.info('Video acquisition is already started.')
            return

        self._child.iq.put('acquire')

        return

    def _stop(self):
        """
        stop video acquisition
        """

        # check that the camera is acquiring
        try:
            assert self._child.acquiring.value == 1
        except AssertionError:
            logging.info('Video acquisition is already stopped.')
            return

        # break out of the acquisition loop
        self._child.acquiring.value = 0

        # retreive the result (sent after exiting the acquisition loop)
        result = self._child.oq.get()

        if not result:
            logging.warning('Video acquisition failed.')

        return

    def set(self, property, value):
        """
        set the value of a valid acquisition property
        """

        # check that the requested property is valid
        try:
            assert property in [CAP_PROP_FPS,CAP_PROP_BINSIZE,CAP_PROP_EXPOSURE]

        except AssertionError:
            logging.warning(f'{property} is not a supported property.')
            return

        # stop the acquisition if started

        # restart acquisition or not
        restart = False

        # if acquisition is ongoing ...
        if self._child.acquiring.value:
            self._stop()
            restart = True

        # communicate with the child process
        self._child.iq.put('set')
        self._child.iq.put(property)
        self._child.iq.put(value)

        result = self._child.oq.get()

        if not result:
            logging.warning(f'Failed to set {property} to {value}.')

        # restart the acquisition if started
        if restart:
            self._start()

        return

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

        # stop video acquisition if ongoing
        if self._child.acquiring.value == 1:
            self._stop()

        # de-init the camera
        self._child.iq.put('deinitialize')
        result = self._child.oq.get()

        if not result:
            logging.warning('Camera de-initialization failed.')

        # break out of the main loop
        self._child.started.value = 0
        self._child.join()

        return
