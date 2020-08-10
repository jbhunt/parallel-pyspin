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

# decorator that handles errors
def spinnaker(method):

    def fwrap(obj, camera):

        try:
            method(obj, camera)
            result = True

        except PySpin.SpinnakerException:
            logging.debug(f"a PySpin exception was raised by the '{method.__name__}' method")
            result = False

        except AssertionError:
            logging.debug(f"an assertion error was raised by the '{method.__name__}' method")
            result = False

        return result

    return fwrap

class SpinnakerMixin(object):
    """
    This mixin contains all of the methods which interact directly with the
    camera via PySpin.

    notes
    -----
    Objects shared between the parent and child process must be serializable.
    For this reason the camera object cannot be stored as a class attribute but
    must instead be created within the scope of the target function. In an
    effort to make the code more readable I created these special methods which
    are called from within the target function of the child process and passed
    the camera object as an argument. The decorator takes each method, calls it,
    and returns the result of the call.
    """

    @spinnaker
    def _initialize(self, camera):
        """
        initialize the camera
        """

        # init the camera
        camera.Init()

        # pixel format
        camera.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)

        # acquisition mode
        camera.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)

        # stream buffer handling mode
        camera.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_NewestOnly)

        # disable auto exposure
        camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)

        return

    @spinnaker
    def _get(self, camera):
        """
        retreive the value of an acquisition property
        """

        property = self._iq.get()

        if property == WIDTH_PROPERTY_ID:
            value = camera.Width.GetValue()
            self._oq.put(value)

        if property == HEIGHT_PROPERTY_ID:
            value = camera.Height.GetValue()
            self._oq.put(value)

        return

    @spinnaker
    def _set(self, camera):
        """
        set the value of an acquisition property
        """

        # retreive the property id and target value
        property = self._iq.get()
        value    = self._iq.get()

        # framerate
        if property == FRAMERATE_PROPERTY_ID:

            # test the requested value
            min  = camera.AcquisitionFrameRate.GetMin()
            max  = camera.AcquisitionFrameRate.GetMax()
            assert min <= value <= max

            # test passed
            camera.AcquisitionFrameRateEnable.SetValue(True)
            camera.AcquisitionFrameRate.SetValue(value)

        # exposure
        if property == EXPOSURE_PROPERTY_ID:

            #
            min = camera.ExposureTime.GetMin()
            max = camera.ExposureTime.GetMax()
            assert min <= value <= max

            #
            camera.AcquisitionFrameRateEnable.SetValue(False)
            camera.ExposureTime.SetValue(value)
            camera.AcquisitionFrameRateEnable.SetValue(True)

        # binsize
        if property == BINSIZE_PROPERTY_ID:

            #
            min = camera.BinningVertical.GetMin()
            max = camera.BinningVertical.GetMax()
            assert min <= value <= max

            #
            camera.BinningHorizontal.SetValue(value)
            camera.BinningVertical.SetValue(value)

        # region of interest
        if property == ROI_PROPERTY_ID:

            # unpack the ROI parameters
            (i, j, h, w) = value

            # test height
            min = camera.Height.GetMin()
            max = camera.Height.GetMax()
            assert min <= h <= max

            # test width
            min = camera.Width.GetMin()
            max = camera.Width.GetMax()
            assert min <= w <= max

            # test x-offset
            min = camera.OffsetY.GetMin()
            max = camera.OffsetY.GetMax()
            assert min <= i <= max

            #
            inc = camera.OffsetX.GetInc()
            assert j % inc == 0

            #
            inc = camera.OffsetY.GetInc()
            assert i % inc == 0

            # test y-offset
            min = camera.OffsetX.GetMin()
            max = camera.OffsetX.GetMax()
            assert min <= j <= max

            # all tests passed
            camera.Height.SetValue(h) # width and height must be set before the offset
            camera.Width.SetValue(w)
            camera.OffsetY.SetValue(i)
            camera.OffsetX.SetValue(j)

        return

    @spinnaker
    def _start(self, camera):
        camera.BeginAcquisition()

    @spinnaker
    def _stop(self, camera):
        camera.EndAcquisition()

    @spinnaker
    def _release(self, camera):
        """
        release the camera
        """

        # double-check that acquisition is stopped
        if camera.IsStreaming():
            camera.EndAcquisition()

        # de-initialize the camera
        camera.DeInit()

        return
