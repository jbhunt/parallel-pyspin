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

class NoCamerasFoundError(Exception):
    """
    """

    def __init__(self):
        """
        """

        super().__init__('No supported cameras were detected.')

        return

class VideoCaptureBase():
    """
    The base class for all video capture subclasses

    keywords
    --------
    device : int or str
        the camera's index or serial number

    private methods
    ---------------
    _run
        target function of the child process
    _initializeChild
        creates and starts the child process
    _destroyChild
        cleans up and joins the child process
    _setAllProperties
        invokes the setter for each property

    special methods - see the note underneath the special methods section
    ---------------
    _initialize
    _set
    _release

    properties
    ----------
    framerate
    exposure
    binsize
    bufferMode
    acquisitionMode
    pixelFormat
    """

    def __init__(self, device):
        """
        """

        self.device = device
        self.child  = None

        # private attributes
        self._started         = mp.Value('i',0) # this flag controls the main loop in the run method
        self._acquiring       = mp.Value('i',0) # this flag controls the acquisition loop in the _start method
        self._iq              = mp.Queue()      # input queue
        self._oq              = mp.Queue()      # output queue

        # continuous acquisition properties
        self._framerate       = constants.FRAMERATE_DEFAULT_VALUE
        self._exposure        = constants.EXPOSURE_DEFAULT_VALUE
        self._binsize         = constants.BINSIZE_DEFAULT_VALUE

        # categorical acquisition properties
        self._bufferMode      = constants.BUFFER_MODE_DEFAULT_VALUE
        self._acquisitionMode = constants.ACQUITISION_MODE_DEFAULT_VALUE
        self._pixelFormat     = constants.ACQUITISION_MODE_DEFAULT_VALUE

        return

    ### private methods - no touchy me ###

    def _run(self):
        """
        target function for the child process

        notes
        -----
        Do not make logging calls (e.g., 'logging.info(<some informative message>)')
        within this method. Writing to stdout is not a process-safe operation.
        """

        # set the started flag to 1
        self.started = 1

        # create instances of the system and cameras
        SYSTEM  = PySpin.System.GetInstance()
        CAMERAS = SYSTEM.GetCameras()

        # assert at least one camera
        if len(CAMERAS) == 0:
            raise NoCamerasFoundError()

        # instantiate the camera
        try:
            if type(self.device) == str:
                camera = CAMERAS.GetBySerial(self.device)
            if type(self.device) == int:
                camera = CAMERAS.GetByIndex(self.device)
            if type(self.device) not in [str,int]:
                raise TypeError(f"The 'device' argument must be a string or integer but is of type {type(self.device)}.")

        except PySpin.SpinnakerException:
            logging.error('Unable to identify the requested camera.')
            return

        # main loop
        while self.started:

            # listen for commands
            try:
                command = self._iq.get(block=False)

            except queue.Empty:
                continue

            # call the appropriate special method

            if command == constants.INITIALIZE:
                result = self._initialize(camera)

            if command == constants.SET:
                result = self._set(camera)

            if command == constants.START:
                result = self._start(camera)

            if command == constants.STOP:
                result = self._stop(camera)

            if command == constants.RELEASE:
                result = self._release(camera)

            # send the result
            self._oq.put(result)

            continue

        # clean up
        try:
            del camera
        except NameError:
            pass
        CAMERAS.Clear()
        SYSTEM.ReleaseInstance()

        return

    def _intitializeChild(self):
        """
        intitialize the child process
        """

        try:
            assert self.child is None
        except AssertionError:
            logging.warning("A child process already exists. To create a new instance call the '_destroyChild' method first.")
            return

        self.child = mp.Process(target=self._run,args=())
        self.child.start()

        return

    def _destroyChild(self):
        """
        destroy the child process
        """

        try:
            assert self.child is not None
        except AssertionError:
            logging.warning("The child process has not been instantiated. Call the '_initializeChild' method.")
            return

        # empty out the queues - if the are not empty it can cause the call to the join method to  hang
        logging.info('Emptying input and output queues.')
        while not self._iq.empty():
            item = self._iq.get()
            logging.info(f"'{item}' removed from the input queue")
        while not self._oq.empty():
            item = self._oq.get()
            logging.info(f"'{item}' removed from the output queue")

        # break out of the main loop in the child process
        try:
            assert self.started == 0
        except AssertionErrort:
            logging.info('Exiting from the child process.')
            self.started = 0

        # join the child process
        try:
            self.child.join(3) # 3" timeout
        except mp.TimeoutError:
            logging.warning('The child process is deadlocked. Terminating.')
            self.child.terminate()
            self.child.join()

        # delete the reference to the child process
        self.child = None

        return

    def _setAllProperties(self):
        """
        set all properties to their current values
        """

        # continuous properties
        self.framerate = self._framerate
        self.exposure  = self._exposure
        self.binsize   = self._binsize

        # categorical properties
        self.bufferMode      = self._bufferMode
        self.acquisitionMode = self._acquisitionMode
        self.pixelFormat     = self._pixelFormat

        return

    ### special methods ###

    # NOTE : Objects shared between the parent and child process must be
    #        process-safe. For this reason the camera object cannot be stored as
    #        a class attribute but must instead be created within the scope of
    #        the target function. In an effort to make the code more readable
    #        I created these special methods which are called from within the
    #        target function of the child process and passed the camera object
    #        as a keyword argument.

    def _initialize(self, camera):
        """
        initialize the camera
        """

        try:
            if not camera.IsInitialized():
                camera.Init()
            result = constants.SUCCESS

        except PySpin.SpinnakerException:
            result = constants.FAILURE

        return result

    def _set(self, camera):
        """
        set the value of an acquisition property
        """

        # retreive the property ID and target value
        property = self._iq.get()
        value    = self._iq.get()

        try:

            # make sure the camera is initialized - necessary for setting properties
            if not camera.IsInitialized():
                camera.Init()

            # TODO - Check if the camera is streaming (maybe stop and restart it?)

            # framerate
            if property == constants.FRAMERATE_ID:
                camera.AcquisitionFrameRateEnable.SetValue(True)
                camera.AcquisitionFrameRate.SetValue(value)

            # exposure
            if property == constants.EXPOSURE_ID:
                camera.AcquisitionFrameRateEnable.SetValue(False)
                camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                camera.ExposureTime.SetValue(value)

            # binsize
            if property == constants.BINSIZE_ID:
                camera.BinningHorizontal.SetValue(self.value)
                camera.BinningVertical.SetValue(self.value)

            # stream buffer handling mode
            if property == constants.BUFFER_MODE_ID:
                tlstreamNodemap = camera.GetTLStreamNodeMap()
                handlingMode = PySpin.CEnumerationPtr(tlstreamNodemap.GetNode('StreamBufferHandlingMode'))
                handlingModeEntry = handlingMode.GetEntryByName(self.value)
                handlingMode.SetIntValue(handlingModeEntry.GetValue())

            # acquisition mode
            if property == constants.ACQUISITION_MODE_ID:
                nodemap = camera.GetNodeMap()
                nodeAcquisitionMode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
                acquisitionModeEntry = nodeAcquisitionMode.GetEntryByName(self.value)
                nodeAcquisitionMode.SetIntValue(acquisitionModeEntry.GetValue())

            # pixel format
            if property == constants.PIXEL_FORMAT_ID:
                nodemap = camera.GetNodeMap()
                nodePixelFormat = PySpin.CEnumerationPtr(nodemap.GetNode('PixelFormat'))
                pixelFormatEntry = PySpin.CEnumEntryPtr(nodePixelFormat.GetEntryByName(self.value))
                nodePixelFormat.SetIntValue(pixelFormatEntry.GetValue())

            result = constants.SUCCESS

        except PySpin.SpinnakerException:
            result = cosntants.FAILURE

        return result

    # NOTE : These '_start' and '_stop' special methods are place-holders. Each
    #        subclass will define its own '_start' and '_stop' special methods.

    def _start(self, camera):
        return constants.ABORTED

    def _stop(self, camera):
        return constants.ABORTED

    def _release(self, camera):
        """
        release the camera
        """

        try:

            # double-check that acquisition is stopped
            if camera.IsStreaming:
                camera.EndAcquisition()

            # de-initialize the camera
            camera.DeInit()

            result = constants.SUCCESS

        except PySpin.SpinnakerException:
            result = constants.FAILURE

        return result

    ### properties ###

    # started flag
    @property
    def started(self): return self._started.value

    @started.setter
    def started(self, value): self._started.value = value

    # acquiring flag
    @property
    def acquiring(self): return self._acquiring.value

    @acquiring.setter
    def acquiring(self, value): self._acquiring.value = value

    # framerate property
    @property
    def framerate(self): return self._framerate

    @framerate.setter
    def framerate(self, value):
        """
        """

        try:
            assert value <= constants.FRAMERATE_MAXIMUM_VALUE
            assert value >= constatns.FRAMERATE_MINIMUM_VALUE
            self._framerate = value

        except:
            message = (
                f'The requested framerate of {value} fps falls outside the range '
                f'of permitted values ({constants.FRAMERATE_MINIMUM_VALUE} - '
                f'{constants.FRAMERATE_MAXIMUM_VALUE} fps). Defaulting to '
                f'{constants.FRAMERATE_DEFAULT_VALUE} fps.'
                )
            logging.warning(message)
            self._framerate = constants.FRAMERATE_DEFAULT_VALUE

        #
        self._iq.put(constants.SET)
        self._iq.put(constants.FRAMERATE_ID) # tell the child what property is being set
        self._iq.put(self._framerate)

        return

    # exposure
    @property
    def exposure(self): return self._exposure

    @exposure.setter
    def exposure(self, value):
        """
        """

        try:
            assert value <= constants.EXPOSURE_MAXIMUM_VALUE
            assert value >= constatns.EXPOSURE_MINIMUM_VALUE
            self._exposure = value

        except:
            message = (
                f'The requested exposure of {value} us falls outside the range '
                f'of permitted values ({constants.EXPOSURE_MINIMUM_VALUE} - '
                f'{constants.EXPOSURE_MAXIMUM_VALUE} us). Defaulting to '
                f'{constants.EXPOSURE_DEFAULT_VALUE} us.'
                )
            logging.warning(message)
            self._exposure = constants.EXPOSURE_DEFAULT_VALUE

        #
        self._iq.put(constants.SET)
        self._iq.put(constants.EXPOSURE_ID) # tell the child what property is being set
        self._iq.put(self._exposure)

        return

    # binsize
    @property
    def binsize(self): return self._binsize

    @binsize.setter
    def binsize(self, value):
        """
        """

        try:
            assert binsize in constants.BINSIZE_PERMITTED_VALUES
            self._binsize = value

        except AssertionError:
            msg = (
                f'The requested binsize value of {value} pixels must belong to '
                f'this set of permitted values : '
                f'{constants.BINSIZE_PERMITTED_VALUES}. Defaulting to '
                f'{constants.BINSIZE_DEFAULT_VALUE} pixels.'
                )
            logging.warning(msg)
            self._binsize = constants.BINSIZE_DEFAULT_VALUE

        #
        self._iq.put(constants.SET)
        self._iq.put(constants.BINSIZE_ID)
        self._iq.put(self._binsize)

        return

    # stream buffer handling mode
    @property
    def bufferMode(self): return self._bufferMode

    @bufferMode.setter
    def bufferMode(self, value):
        pass

    # acquisition mode
    @property
    def acquisitionMode(self): return self._acquisitionMode

    @acquisitionMode.setter
    def acquisitionMode(self, value):
        pass

    # pixel format
    @property
    def pixelFormat(self): return self._pixelFormat

    @pixelFormat.setter
    def pixelFormat(self, value):
        pass

class VideoCameraMixin():
    """
    a mixin class which defines the methods and properties shared
    between primary and secondary cameras
    """

    def release(self):
        """
        release the camera
        """

        # stop acquisition if acquiring
        if self.primed:
            logging.info('Stopping video acquisition.')
            self.stop()

        #
        self._iq.put(constants.RELEASE)
        result = self._oq.get()
        if not result:
            logging.warning('Camera de-initialization failed.')

        # stop and join the child process
        self._destroyChild()

        return

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
