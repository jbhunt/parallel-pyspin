import types
import queue
import logging
import numpy as np
import multiprocessing as mp
from llpyspin import constants

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.DEBUG)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

class SpinnakerMethod(object):
    """
    a decorator for methods which directly interact with the camera via PySpin
    """

    def __init__(self, method=None):
        self.method = method

    def __get__(self, obj, cls): return types.MethodType(self, obj) if obj else self

    def __call__(self, obj, camera):
        if self.method is None:
            raise AttributeError('no method given to the constructor')
        try:
            self.method(obj, camera)
            return constants.SUCCESS
        except PySpin.SpinnakerException:
            loging.debug('"SpinnakerMethod" decorated method raised an exception.')
            return constants.FAILURE

class AcquisitionProperty(object):
    """
    a pure Python implementation of properties with the additional functionality
    to check that the value of the property to-set passes a check defined by the
    checker method, i.e., the call to the property's __set__ method is dependent
    upon the result of the call to the __check__ method.

    notes
    -----
    An instance of this class will function exactly like a property unless the
    'checker' method is defined via decoration.

    references
    ----------
    [1] https://docs.python.org/3/howto/descriptor.html#properties
    """

    def __init__(self, fget=None, fset=None, fdel=None, fcheck=None, doc=None):
        self.fget   = fget
        self.fset   = fset
        self.fdel   = fdel
        self.fcheck = fcheck
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError("unreadable attribute")
        return self.fget(obj)

    def __set__(self, obj, value):
        """
        """

        if self.fset is None:
            raise AttributeError("can't set attribute")

        # perform the check
        result = self.__check__(obj, value)

        # check passed
        if result:

            # pause acquiition
            try: assert obj.acquiring == False; restart = False
            except AssertionError:
                logging.debug('Pausing acquisition.')
                obj.acquiring = False
                result = obj._oq.get()
                if not result: logging.debug('Video acquisition failed.')
                obj._iq.put(constants.STOP)
                result = obj._oq.get()
                if not result: logging.debug('Video de-acquisition failed')
                restart = True

            # call the fset method
            self.fset(obj, value)

            # restart acquisition
            if restart:
                logging.debug('Unpausing acquisition.')
                obj.acquiring = True
                obj._iq.put(constants.START)

        # check failed
        else:
            raise ValueError("value to-set did not pass check")

    def __delete__(self, obj):
        if self.fdel is None:
            raise AttributeError("can't delete attribute")
        self.fdel(obj)

    def __check__(self, obj, value):
        if self.fcheck is None:
            return True # passes the check unless fcheck is defined
        return self.fcheck(obj, value)

    def getter(self, fget):
        return type(self)(fget, self.fset, self.fdel, self.fcheck, self.__doc__)

    def setter(self, fset):
        return type(self)(self.fget, fset, self.fdel, self.fcheck, self.__doc__)

    def deleter(self, fdel):
        return type(self)(self.fget, self.fset, fdel, self.fcheck, self.__doc__)

    def checker(self, fcheck):
        return type(self)(self.fget, self.fset, self.fdel, fcheck, self.__doc__)

class VideoCameraBase():
    """
    This is the base class which contains the __init__ method and whatever other
    methods don't belong to one of the Mixin classes.
    """

    def __init__(self, device):
        """
        keywords
        --------
        device : int or str
            the camera's index or serial number
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
        self._buffermode      = constants.BUFFER_MODE_DEFAULT_VALUE
        self._acquisitionmode = constants.ACQUISITION_MODE_DEFAULT_VALUE
        self._pixelformat     = constants.PIXEL_FORMAT_DEFAULT_VALUE

        return

    def _setall(self):
        """
        set all properties to their current values
        """

        self.framerate = self._framerate
        self.exposure  = self._exposure
        self.binsize   = self._binsize

        self.acquisitionmode = self._acquisitionmode
        self.buffermode      = self._buffermode
        self.pixelformat     = self._pixelformat

        return

    # started flag
    @property
    def started(self): return True if self._started.value == 1 else False

    @started.setter
    def started(self, value):
        self._started.value = 1 if value == True else False

    # acquiring flag
    @property
    def acquiring(self): return True if self._acquiring.value == 1 else False

    @acquiring.setter
    def acquiring(self, value):
        self._acquiring.value = 1 if value == True else False

class ChildProcessMixin(object):
    """
    This mixin contains all of the methods which handle the creation, opertation,
    and destruction of the child process.
    """

    def _run(self):
        """
        target function for the child process

        notes
        -----
        Do not make logging calls (e.g., 'logging.info(<some informative message>)')
        within this method. Writing to stdout is not a process-safe operation.
        """

        # create instances of the system and cameras
        system  = PySpin.System.GetInstance()
        cameras = system.GetCameras()

        # assert at least one camera
        if len(cameras) == 0:
            raise NoCamerasFoundError()

        # instantiate the camera
        try:

            if type(self.device) == str:
                camera = cameras.GetBySerial(self.device)

            if type(self.device) == int:
                camera = cameras.GetByIndex(self.device)

            if type(self.device) not in [str,int]:
                cameras.Clear()
                system.ReleaseInstance()
                raise TypeError(f"The 'device' argument must be a string or integer but is of type '{type(self.device)}'.")

        except PySpin.SpinnakerException:
            logging.error('Unable to create an instance of the camera.')
            return

        # set the started flag to True
        self.started = True

        # main loop
        while self.started:

            # listen for commands
            try:
                item = self._iq.get(block=False)

            except queue.Empty:
                continue

            # call the appropriate method

            if item == constants.INITIALIZE:
                result = self._initialize(camera)

            elif item == constants.SET:
                result = self._set(camera)

            elif item == constants.START:
                result = self._start(camera)

            elif item == constants.STOP:
                result = self._stop(camera)

            elif item == constants.RELEASE:
                result = self._release(camera)

            else:
                logging.info(f'The input queue received an invalid item : "{item}".')
                result = False

            # send the result
            self._oq.put(result)

            continue

        # clean up
        try:
            del camera
        except NameError:
            pass
        cameras.Clear()
        system.ReleaseInstance()

        return

    def _create(self):
        """
        create the child process
        """

        try:
            assert self.child is None
        except AssertionError:
            logging.warning("A child process already exists. To create a new instance call the '_destroy' method first.")
            return

        logging.debug('Creating the child process.')

        self.child = mp.Process(target=self._run,args=())
        self.child.start()

        return

    def _destroy(self):
        """
        destroy the child process
        """

        try:
            assert self.child is not None
        except AssertionError:
            logging.warning("No child process exists. Create the child process with the '_create' method.")
            return

        logging.debug('Destroying the child process.')

        # break out of the main loop in the child process
        self.started = False

        # empty out the queues - if the are not empty it can cause the call to the join method to  hang
        if self._iq.qsize() != 0 or self._oq.qsize() != 0:
            logging.info('Emptying input and output queues.')
            while not self._iq.empty():
                item = self._iq.get()
                logging.info(f"'{item}' removed from the input queue")
            while not self._oq.empty():
                item = self._oq.get()
                logging.info(f"'{item}' removed from the output queue")

        # join the child process
        try:
            self.child.join(1) # 1" timeout
        except mp.TimeoutError:
            logging.warning('The child process is deadlocked. Terminating.')
            self.child.terminate()
            self.child.join()

        # delete the reference to the child process
        self.child = None

        # spawn a new child process
        # self._create()

        return

class SpinnakerMethodsMixin(object):
    """
    This mixin contains all of the methods which interact directly with the
    camera via PySpin.

    notes
    -----
    Objects shared between the parent and child process must be process-safe.
    For this reason the camera object cannot be stored as a class attribute but
    must instead be created within the scope of the target function. In an
    effort to make the code more readable I created these special methods which
    are called from within the target function of the child process and passed
    the camera object as an argument. The decorator takes each method, calls it,
    and returns the result of the call.
    """

    @SpinnakerMethod
    def _initialize(self, camera):
        """
        initialize the camera
        """

        camera.Init()

        return

    @SpinnakerMethod
    def _set(self, camera):
        """
        set the value of an acquisition property
        """

        # retreive the property name and target value
        id    = self._iq.get()
        value = self._iq.get()

        # framerate
        if id == constants.FRAMERATE_ID:
            camera.AcquisitionFrameRateEnable.SetValue(True)
            camera.AcquisitionFrameRate.SetValue(value)

        # exposure
        elif id == constants.EXPOSURE_ID:
            camera.AcquisitionFrameRateEnable.SetValue(False)
            camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
            camera.ExposureTime.SetValue(value)
            camera.AcquisitionFrameRateEnable.SetValue(True)

        # binsize
        elif id == constants.BINSIZE_ID:
            camera.BinningHorizontal.SetValue(value)
            camera.BinningVertical.SetValue(value)

        # stream buffer handling mode
        elif id == constants.BUFFER_MODE_ID:
            tlstreamNodemap = camera.GetTLStreamNodeMap()
            handlingMode = PySpin.CEnumerationPtr(tlstreamNodemap.GetNode('StreamBufferHandlingMode'))
            handlingModeEntry = handlingMode.GetEntryByName(value)
            handlingMode.SetIntValue(handlingModeEntry.GetValue())

        # acquisition mode
        elif id == constants.ACQUISITION_MODE_ID:
            nodemap = camera.GetNodeMap()
            nodeAcquisitionMode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
            acquisitionModeEntry = nodeAcquisitionMode.GetEntryByName(value)
            nodeAcquisitionMode.SetIntValue(acquisitionModeEntry.GetValue())

        # pixel format
        elif id == constants.PIXEL_FORMAT_ID:
            nodemap = camera.GetNodeMap()
            nodePixelFormat = PySpin.CEnumerationPtr(nodemap.GetNode('PixelFormat'))
            pixelFormatEntry = PySpin.CEnumEntryPtr(nodePixelFormat.GetEntryByName(value))
            nodePixelFormat.SetIntValue(pixelFormatEntry.GetValue())

        # raise the SpinnakerException
        else:
            raise PySpin.SpinnakerException

        return

    @SpinnakerMethod
    def _start(self, camera):
        """
        """

        camera.BeginAcquisition()

        return

    @SpinnakerMethod
    def _stop(self, camera):
        """
        """

        camera.EndAcquisition()

        return

    @SpinnakerMethod
    def _release(self, camera):
        """
        release the camera
        """

        # double-check that acquisition is stopped
        try:
            assert camera.IsStreaming() == False
        except AssertionError:
            camera.EndAcquisition()

        # de-initialize the camera
        camera.DeInit()

        return

class AcquisitionPropertiesMixin(object):
    """
    This mixin contains all the video acquisition property definitions.
    """

    # framerate property
    @AcquisitionProperty
    def framerate(self): return self._framerate

    @framerate.checker
    def framerate(self, value):
        return True if constants.FRAMERATE_MINIMUM_VALUE <= value <= constants.FRAMERATE_MAXIMUM_VALUE else False

    @framerate.setter
    def framerate(self, value):
        """
        """

        self._framerate = value

        self._iq.put(constants.SET)
        self._iq.put(constants.FRAMERATE_ID) # tell the child what property is being set
        self._iq.put(self._framerate)

        logging.info(f'Setting framerate to {value} fps.')

        result = self._oq.get()
        if not result:
            logging.warning(f'Failed to set the framerate to "{value}" fps.')

    # exposure
    @AcquisitionProperty
    def exposure(self): return self._exposure

    @exposure.checker
    def exposure(self, value):
        return True if constants.EXPOSURE_MINIMUM_VALUE <= value <= constants.EXPOSURE_MAXIMUM_VALUE else False

    @exposure.setter
    def exposure(self, value):
        """
        """

        self._exposure = value

        self._iq.put(constants.SET)
        self._iq.put(constants.EXPOSURE_ID) # tell the child what property is being set
        self._iq.put(self._exposure)

        logging.info(f'Setting exposure to {value} us.')

        result = self._oq.get()
        if not result:
            logging.warning(f'Failed to set the exposure to "{value}" us.')

    # binsize
    @AcquisitionProperty
    def binsize(self): return self._binsize

    @binsize.checker
    def binsize(self, value):
        return True if value in constants.BINSIZE_PERMITTED_VALUES else False

    @binsize.setter
    def binsize(self, value):
        """
        """

        self._binsize = value

        self._iq.put(constants.SET)
        self._iq.put(constants.BINSIZE_ID)
        self._iq.put(self._binsize)

        logging.info(f'Setting binsize to {value} pixels.')

        result = self._oq.get()
        if not result:
            logging.warning(f'Failed to set the binsize to "{value}" pixel(s).')

    # stream buffer handling mode
    @AcquisitionProperty
    def buffermode(self): return self._buffermode

    @buffermode.checker
    def buffermode(self, value):
        return True if value in constants.BUFFER_MODE_PERMITTED_VALUES else False

    @buffermode.setter
    def buffermode(self, value):
        """
        """

        self._buffermode = value

        self._iq.put(constants.SET)
        self._iq.put(constants.BUFFER_MODE_ID)
        self._iq.put(self._buffermode)

        logging.info(f'Setting buffer mode to "{value}".')

        result = self._oq.get()
        if not result:
            logging.warning(f'Failed to set the stream buffer handling mode to "{value}".')

    # acquisition mode
    @AcquisitionProperty
    def acquisitionmode(self): return self._acquisitionmode

    @acquisitionmode.checker
    def acquisitionmode(self, value):
        return True if value in constants.ACQUISITION_MODE_PERMITTED_VALUES else False

    @acquisitionmode.setter
    def acquisitionmode(self, value):
        """
        """

        self._acquisitionmode = value

        self._iq.put(constants.SET)
        self._iq.put(constants.ACQUISITION_MODE_ID)
        self._iq.put(self._acquisitionmode)

        logging.info(f'Setting acquisition mode to "{value}".')

        result = self._oq.get()
        if not result:
            logging.warning(f'Failed to set the acquisition mode to "{value}".')

    # pixel format
    @AcquisitionProperty
    def pixelformat(self): return self._pixelformat

    @pixelformat.checker
    def pixelformat(self, value):
        return True if value in constants.PIXEL_FORMAT_PERMITTED_VALUES else False

    @pixelformat.setter
    def pixelformat(self, value):
        """
        """

        self._pixelformat = value

        self._iq.put(constants.SET)
        self._iq.put(constants.PIXEL_FORMAT_ID)
        self._iq.put(self._pixelformat)

        logging.debug(f'Setting pixel format to "{value}".')

        result = self._oq.get()
        if not result:
            logging.warning(f'Failed to set the pixel format to "{value}".')
