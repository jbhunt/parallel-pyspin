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
        self._framerate = c.CAP_PROP_FPS_DEFAULT
        self._binsize   = c.CAP_PROP_BINSIZE_DEFAULT
        self._exposure  = c.CAP_PROP_EXPOSURE_DEFAULT
        self._mode      = c.CAP_PROP_BUFFER_HANDLING_MODE_STREAMING

        # start acquisition
        self.open()

        return

    def _startChild(self):
        """
        start the child process
        """

        self._child = p.VideoStreamProcess(self.device)
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
            self._mode
            ]

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
            logging.warning(f'{property} is not a valid property.')
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

        # break out of the main loop
        self._child.started.value = 0
        self._child.join()

        return

class BaseCamera():
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

        #
        self.serialno  = serialno # camera serial number
        self._nickname = nickname # camera nickname
        self._child    = None # child process
        self._primed   = False

        # default capture properties
        self._framerate = c.CAP_PROP_FPS_DEFAULT
        self._binsize   = c.CAP_PROP_BINSIZE_DEFAULT
        self._exposure  = c.CAP_PROP_EXPOSURE_DEFAULT
        self._mode      = c.CAP_PROP_BUFFER_HANDLING_MODE_RECORDING

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
            self._child.join(3) # 3 second timeout
        except TimeoutError:
            logging.warning('The child process is deadlocked. Terminating.')
            self._child.terminate()
            self._child.join()

        # delete the process instance
        self._child = None

        return

    def _resetProperties(self):
        """
        set the capture properties to their current values
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
            self._mode
            ]

        for property,value in zip(properties,values):
            result = self._set(property,value)
            if not result:
                logging.warning(f'Failed to set {property} to {value}.')

        return

    def release(self):
        """
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
        self._child.started.value = 0
        self._child.join()

        return

    def _set(self, property, value):
        """
        set the value of a valid acquisition property

        returns
        -------
        result : bool
            True if successul in setting new value of property else False
        """

        result = False

        # assert that acquisition is not ongoing
        try:
            assert self.isPrimed() is False
        except AssertionError:
            logging.warning(f'Failed to set {property} to {value} because video acquisition is ongoing.')
            return result

        # check that the requested property is valid
        try:
            assert property in c.SUPPORTED_CAP_PROPS

        except AssertionError:
            logging.warning(f'Failed to set {property} to {value} because {property} is not a valid property.')
            return result

        # stop the acquisition if started

        # communicate with the child process
        self._child.iq.put('set')
        self._child.iq.put(property)
        self._child.iq.put(value)

        logging.info(f'Setting {property} to {value}.')

        result = self._child.oq.get()

        if not result:
            logging.warning(f'Failed to set {property} to {value}.')

        return result

    # framerate
    @property
    def framerate(self):
        return self._framerate
    @framerate.setter
    def framerate(self, value):
        result = self._set(c.CAP_PROP_FPS,value)
        if result:
            self._framerate = value

    # exposure
    @property
    def exposure(self):
        return self._exposure
    @exposure.setter
    def exposure(self, value):
        result = self._set(c.CAP_PROP_EXPOSURE,value)
        if result:
            self._exposure = value

    # binsize
    @property
    def binsize(self):
        return self._binsize
    @binsize.setter
    def binsize(self, value):
        result = self._set(c.CAP_PROP_BINSIZE,value)
        if result:
            self._binsize = value

    # buffer stream handling mode
    @property
    def mode(self):
        return self._mode
    @mode.setter
    def mode(self, value):
        result = self._set(c.CAP_PROP_BUFFER_HANDLING_MODE,value)
        if result:
            self._mode = value

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
        logging.warning('The "primed" attribute cannot be set manually.')

class PrimaryCamera(BaseCamera):
    """
    """

    def __init__(self, serialno, nickname=None):
        """
        """

        super().__init__(serialno, nickname)

        # camera ready state
        self._primed = False

        # camera trigger state
        self._triggered = False

        # prime the camera
        self.prime()

        return

    def _initializeChild(self):
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
        self._child = p.PrimaryCameraProcess(self.serialno)

        # start the child process
        self._child.start()

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
        self._initializeChild()

        # initialize the camera
        self._child.iq.put('initialize')
        result = self._child.oq.get()
        if not result:
            logging.error('Camera initialization failed.')
            return

        # set the acquisition properties
        self._resetProperties()

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

        self._triggered = True
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
        self._triggered = value

class SecondaryCamera(BaseCamera):
    """
    """

    def __init__(self, icamera=0, serialno=None, nickname=None):
        """
        """

        super().__init__(serialno, nickname)

        # serial number
        self.serialno = c.SECONDARY_SERIALNOS[icamera] if serialno is None else serialno

        # nickname
        self.nickname = c.SECONDARY_NICKNAMES[icamera] if nickname is None else nickname

        self.prime()

        return

    def _createChild(self):
        """
        create and start the child process
        """

        self._child = p.SecondaryCameraProcess(self.serialno)
        self._child.start()

        return

    def prime(self):
        """
        prime the camera for video acquisition
        """

        # check that the camera isn't acquiring
        try:
            assert self.isPrimed() is False
        except AssertionError:
            logging.info('Video acquisition is already started.')
            return

        # (re-)start the child process if needed
        if not hasattr(self,'_child') or not self._child.is_alive(): # the order of these conditions is important
            self._createChild()

        # initialize the camera
        self._child.iq.put('initialize')
        result = self._child.oq.get()
        if not result:
            logging.error('Camera initialization failed.')
            return

        # set the acquisition properties
        for (property,value) in vars(self).items():
            property = property.strip('_')
            if property in c.SUPPORTED_CAP_PROPS:
                result = self._set(property,value)

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
            assert self.isPrimed() is True
        except AssertionError:
            logging.info('Video acquisition is already stopped.')
            return

        # break out of the acquisition loop
        self._child.acquiring.value = 0

        # NOTE : Be very careful here. If the hardware trigger was never detected,
        # the child process will block indefinitely causing the get call below
        # to block the parent process. To avoid this, there is a timeout on the
        # get call. In the case of a timeout, the child process is terminated.

        try:
            result = self._child.oq.get(block=True,timeout=5)
            if not result:
                logging.warning('Video acquisition failed.')

        except Empty:

            # TODO : Instead of terminating the child process,
            # send all the commands to clean up then join the process

            # log this event
            logging.warning('The hardware trigger was never detected.')

            # kill the child process
            self._child.terminate()
            self._child.join()

            # restart the child process
            self._createChild()

            return

        # stop acquisition
        self._child.iq.put('deacquire')
        result = self._child.oq.get()

        # check result
        if not result:
            logging.warning('Failed to stop video acquisition.')

        return
