import types
import logging

# constants
from ._constants import *

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.DEBUG)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

class SpinnakerMethod(object):
    """
    a decorator for methods which interact with the camera directly via PySpin
    """

    def __init__(self, method=None):
        self.method = method

    def __get__(self, obj, cls): return types.MethodType(self, obj) if obj else self

    def __call__(self, obj, camera):
        if self.method is None:
            raise AttributeError('no method given to the constructor')
        try:
            self.method(obj, camera)
            return SUCCESS
        except PySpin.SpinnakerException:
            logging.debug('"SpinnakerMethod" decorated method raised an exception.')
            return FAILURE

class SpinnakerMixin(object):
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

        # super(SpinnakerMixin, self)._initialize(self, camera)

        camera.Init()

        # the only supported pixel format it 'Mono8'
        nodemap = camera.GetNodeMap()
        nodePixelFormat = PySpin.CEnumerationPtr(nodemap.GetNode('PixelFormat'))
        pixelFormatEntry = PySpin.CEnumEntryPtr(nodePixelFormat.GetEntryByName('Mono8'))
        nodePixelFormat.SetIntValue(pixelFormatEntry.GetValue())

        #
        nodemap = camera.GetNodeMap()
        nodeAcquisitionMode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
        acquisitionModeEntry = nodeAcquisitionMode.GetEntryByName('Continuous')
        nodeAcquisitionMode.SetIntValue(acquisitionModeEntry.GetValue())

        #
        tlstreamNodemap = camera.GetTLStreamNodeMap()
        handlingMode = PySpin.CEnumerationPtr(tlstreamNodemap.GetNode('StreamBufferHandlingMode'))
        handlingModeEntry = handlingMode.GetEntryByName('OldestFirst')
        handlingMode.SetIntValue(handlingModeEntry.GetValue())

        return

    @SpinnakerMethod
    def _set(self, camera):
        """
        set the value of an acquisition property
        """

        # super(SpinnakerMixin, self)._set(self, camera)

        # retreive the property name and target value
        id    = self._iq.get()
        value = self._iq.get()

        # framerate
        if id == FRAMERATE_PROPERTY_ID:
            camera.AcquisitionFrameRateEnable.SetValue(True)
            camera.AcquisitionFrameRate.SetValue(value)

        # exposure
        elif id == EXPOSURE_PROPERTY_ID:
            camera.AcquisitionFrameRateEnable.SetValue(False)
            camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
            camera.ExposureTime.SetValue(value)
            camera.AcquisitionFrameRateEnable.SetValue(True)

        # binsize
        elif id == BINSIZE_PROPERTY_ID:
            camera.BinningHorizontal.SetValue(value)
            camera.BinningVertical.SetValue(value)

        return

    @SpinnakerMethod
    def _start(self, camera):
        # super(SpinnakerMixin, self)._start(self, camera)
        camera.BeginAcquisition()

    @SpinnakerMethod
    def _stop(self, camera):
        # super(SpinnakerMixin, self)._stop(self, camera)
        camera.EndAcquisition()

    @SpinnakerMethod
    def _release(self, camera):
        """
        release the camera
        """

        # super(SpinnakerMixin, self)._release(self, camera)

        # double-check that acquisition is stopped
        try:
            assert camera.IsStreaming() == False
        except AssertionError:
            logging.debug('The camera was not stopped before trying to release it.')
            camera.EndAcquisition()

        # de-initialize the camera
        camera.DeInit()

        return
