# imports
import logging
import numpy as np
from queue import Empty
from multiprocessing import TimeoutError

# relative imports
import llpyspin.constants as c
import llpyspin.processes as p

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

class ChildProcessWrapper():
    """
    """

    def __init__(self):
        """
        """

        self._child      = None
        self._framerate  = c.CAP_PROP_FPS_DEFAULT
        self._binsize    = c.CAP_PROP_BINSIZE_DEFAULT
        self._exposure   = c.CAP_PROP_EXPOSURE_DEFAULT
        self._buffermode = c.CAP_PROP_BUFFER_HANDLING_MODE_STREAMING

        return

    def _initializeChild(self, childClass):
        """
        initialize (or re-initialize) the child process
        """

        # destroy the child process if one already exists
        try:
            assert self._child is None

        except AssertionError:

            # log this event
            logging.info('Restarting the child process.')

            # destroy the child
            self._destroyChild()

        # (re-)instantiate the child process
        self._child = childClass(self.serialno)

        # start the child process
        self._child.start()

        return

    def _destroyChild(self):
        """
        destroy the child process
        """

        # empty out the input and output queues - if the queues aren't empty the process can hang
        while self._child.iq.qsize() != 0:
            result = self._child.iq.get()

        while self._child.oq.qsize() != 0:
            result = self._child.oq.get()

        # break out of the main loop
        self._child.started.value = 0

        # try to join the child process with the parent process
        try:
            self._child.join(5) # 5 second timeout
        except TimeoutError:
            logging.warning('The child process is deadlocked. Terminating.')
            self._child.terminate()
            self._child.join()

        # delete the process instance
        self._child = None

        return

    def _setProperty(self, property, value):
        """
        set the value of a valid acquisition property

        returns
        -------
        result : bool
            True if successful in setting new value of property else False
        """

        result = False

        # assert that acquisition is not ongoing
        try:
            assert self._child.acquiring.value == 0

        except AssertionError:
            logging.warning(f'Failed to set {property} to {value} because video acquisition is ongoing.')
            return result

        # check that the requested property is valid
        try:
            assert property in c.SUPPORTED_CAP_PROPS

        except AssertionError:
            logging.warning(f'Failed to set {property} to {value} because {property} is not a valid property.')
            return result

        # communicate with the child process
        self._child.iq.put('set')
        self._child.iq.put(property)
        self._child.iq.put(value)

        logging.info(f'Setting {property} to {value}.')

        result = self._child.oq.get()

        if not result:
            logging.warning(f'Failed to set {property} to {value}.')

        return result

    def _resetAllProperties(self):
        """
        set all the capture properties to their current values
        """

        properties = [
            c.CAP_PROP_FPS,
            c.CAP_PROP_BINSIZE,
            c.CAP_PROP_EXPOSURE,
            c.CAP_PROP_BUFFER_HANDLING_MODE
            ]

        values = [
            self._framerate,
            self._binsize,
            self._exposure,
            self._buffermode
            ]

        for property,value in zip(properties,values):
            result = self._setProperty(property,value)

        return

class VideoStream(ChildProcessWrapper):
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

        super().__init__()

        #
        self.device = device

        # start acquisition
        self.open()

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

        # initialize the child process
        self._initializeChild(childClass=p.VideoStreamProcess)

        # initialize the camera
        self._child.iq.put('initialize')
        result = self._child.oq.get()
        if not result:
            logging.error('Camera initialization failed.')
            return

        # set all the capture properties
        self._resetAllProperties()

        # start the video acquisition
        self._child.iq.put('acquire')

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
                image = np.array(self._child.image[:],dtype=np.uint8).reshape(c.IMAGE_SHAPE)

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

        # destroy the child process
        self._destroyChild()

        return

    def set(self, property, value):
        """
        set the value of a valid acquisition property
        """

        # check that the requested property is valid
        try:
            assert property in c.SUPPORTED_CAP_PROPS

        except AssertionError:
            logging.warning(f'{property} is not a supported property.')
            return

        #
        if self.isOpened():
            self.release()

        # update the value of the class attribute
        self.__setattr__(f'_{property}',value)

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
            logging.warning(f'{property} is not a supported property')

        value = self.__getattribute__(f'_{property}')

        return value

class BaseCamera(ChildProcessWrapper):
    """
    """

    def __init__(self, serialno, nickname=None):
        """
        """

        try:
            assert type(serialno) == str:
        except AssertionError:
            logging.error(f'The serial number must be a string.')
            return

        super().__init__()

        #
        self.serialno  = serialno # camera serial number
        self._nickname = nickname # camera nickname
        self._primed   = False

        return

    def release(self):
        """
        release the camera
        """

        # stop acquisition if acquiring
        if self.primed is True:
            logging.info('Stopping video acquisition.')
            self.stop()

        # deconfigure camera
        self._child.iq.put('deconfigure')
        result = self._child.oq.get()
        if not result:
            logging.warning('Camera deconfiguration failed.')

        # de-init the camera
        self._child.iq.put('deinitialize')
        result = self._child.oq.get()
        if not result:
            logging.warning('Camera deinitialization failed.')

        # stop and join the child process
        self._destroyChild()

        return

    ### properties ###

    # framerate
    @property
    def framerate(self):
        return self._framerate
    @framerate.setter
    def framerate(self, value):
        result = self._setProperty(c.CAP_PROP_FPS,value)
        if result:
            self._framerate = value

    # exposure
    @property
    def exposure(self):
        return self._exposure
    @exposure.setter
    def exposure(self, value):
        result = self._setProperty(c.CAP_PROP_EXPOSURE,value)
        if result:
            self._exposure = value

    # binsize
    @property
    def binsize(self):
        return self._binsize
    @binsize.setter
    def binsize(self, value):
        result = self._setProperty(c.CAP_PROP_BINSIZE,value)
        if result:
            self._binsize = value

    # stream buffer handling mode
    @property
    def buffermode(self):
        return self._buffermode
    @buffermode.setter
    def buffermode(self, value):
        result = self._setProperty(c.CAP_PROP_BUFFER_HANDLING_MODE,value)
        if result:
            self._buffermode = value

    # nickname
    @property
    def nickname(self):
        return self._nickname
    @nickname.setter
    def nickname(self, value):
        self._nickname = value

    # camera ready state
    @property
    def primed(self):
        self._primed = True if self._child is not None and self._child.acquiring.value == 1 else False
        return self._primed
    @primed.setter
    def primed(self, value):
        logging.warning("The 'primed' attribute can't be set manually.")

class PrimaryCamera(BaseCamera):
    """
    """

    def __init__(self, serialno, nickname=None):
        """
        """

        super().__init__(serialno, nickname)

        # camera trigger state
        self._triggered = False

        # prime the camera
        self.prime()

        return

    def prime(self):
        """
        prime the camera for video acquisition
        """

        # check that the camera isn't acquiring
        try:
            assert self.primed is False
        except AssertionError:
            logging.info('Video acquisition is already started.')
            return

        # intitialize (or re-initialize) the child process
        self._initializeChild(childClass=p.PrimaryCameraProcess)

        # initialize the camera
        self._child.iq.put('initialize')
        result = self._child.oq.get()
        if not result:
            logging.error('Camera initialization failed.')
            return

        # set the acquisition properties
        self._resetAllProperties()

        # configure the camera
        self._child.iq.put('configure')
        result = self._child.oq.get()
        if not result:
            logging.error('Camera configuration failed.')
            return

        # set the acquiring flag to 1
        self._child.acquiring.value = 1

        # send the acquisition command
        self._child.iq.put('acquire')

        # set the triggered flag to False
        self._triggered = False

        return

    def trigger(self):
        """
        trigger the master camera
        """

        # start acquisition if necessary
        if not self.primed:
            logging.warning('Video acquisition is not started. Call the prime method.')
            return

        # set the triggered flag to True
        self._triggered = True

        # send the trigger state to the child process
        self._child.iq.put(self._triggered)

        return

    def stop(self):
        """
        stop video acquisition
        """

        # check that the camera is acquiring
        try:
            assert self.primed is True
        except AssertionError:
            logging.info('Video acquisition is already stopped.')
            return

        # release the trigger if the camera is still waiting for it
        if not self._triggered:
            self._child.iq.put(self._triggered)

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
            logging.warning('Failed to stop video acquisition.')

        return

    # camera trigger state
    @property
    def triggered(self):
        return self._triggered
    @triggered.setter
    def triggered(self, value):
        logging.warning("The 'trigger' attribute can't be set manually")

class SecondaryCamera(BaseCamera):
    """
    """

    def __init__(self, serialno, nickname=None):
        """
        """

        super().__init__(serialno, nickname)

        self.prime()

        return

    def prime(self):
        """
        prime the camera for video acquisition
        """

        # check that the camera isn't acquiring
        try:
            assert self.primed is False
        except AssertionError:
            logging.info('Video acquisition is already started.')
            return

        # initialize the child process
        self._initializeChild(chidClass=p.SecondaryCameraProcess)

        # initialize the camera
        self._child.iq.put('initialize')
        result = self._child.oq.get()
        if not result:
            logging.error('Camera initialization failed.')
            return

        # set the acquisition properties
        self._resetAllProperties()

        # configure the camera
        self._child.iq.put('configure')
        result = self._child.oq.get()
        if not result:
            logging.error('Camera configuration failed.')
            return

        self._child.iq.put('acquire')

        return

    def stop(self):
        """
        stop video acquisition
        """

        # check that the camera is acquiring
        try:
            assert self.primed is True
        except AssertionError:
            logging.info('Video acquisition is already stopped.')
            return

        # break out of the acquisition loop
        self._child.acquiring.value = 0

        # this get call shouldn't ever hang now but you never know
        result = self._child.oq.get()
        if not result:
            logging.warning('Video acquisition failed.')

        # stop acquisition
        self._child.iq.put('deacquire')
        result = self._child.oq.get()

        # check result
        if not result:
            logging.warning('Failed to stop video acquisition.')

        return
