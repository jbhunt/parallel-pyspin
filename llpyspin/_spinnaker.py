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

        except PropertyValueError as error:
            logging.debug(error.message)
            result = False

        # except:
        #     logging.debug('undefined error raised by a spinnaker method')
        #     result = False

        return result

    return fwrap

class PropertyValueError(Exception):
    """error raised for failed attempts to set the value of an acquisition property"""

    def __init__(self, property, value):
        super().__init__()
        self.message = f'{value} is an invalid value for {property}'

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

        if property == FRAMERATE_PROPERTY_ID:
            value = camera.AcquisitionFrameRate.GetMax()

        if property == WIDTH_PROPERTY_ID:
            value = camera.Width.GetMax()

        if property == HEIGHT_PROPERTY_ID:
            value = camera.Height.GetMax()

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
            if not min <= value <= max:
                raise PropertyValueError('framerate', value)

            # test passed
            camera.AcquisitionFrameRateEnable.SetValue(True)
            camera.AcquisitionFrameRate.SetValue(value)

        # exposure
        if property == EXPOSURE_PROPERTY_ID:

            #
            min = camera.ExposureTime.GetMin()
            max = camera.ExposureTime.GetMax()
            if not min <= value <= max:
                raise PropertyValueError('exposure', value)

            #
            camera.AcquisitionFrameRateEnable.SetValue(False)
            camera.ExposureTime.SetValue(value)
            camera.AcquisitionFrameRateEnable.SetValue(True)

        # binsize
        if property == BINSIZE_PROPERTY_ID:

            #
            min = camera.BinningVertical.GetMin()
            max = camera.BinningVertical.GetMax()
            if not min <= value <= max:
                raise PropertyValueError('binsize',  value)

            # TODO : check that the value is a valid increment of each bin axis

            #
            camera.BinningHorizontal.SetValue(value)
            camera.BinningVertical.SetValue(value)

        # region of interest
        if property == ROI_PROPERTY_ID:

            # unpack the ROI parameters
            (y, x, h, w) = value # TODO : change the order of parameters to x, y, w, h

            # test height
            min = camera.Height.GetMin()
            max = camera.Height.GetMax()
            if not min <= h <= max:
                raise PropertyValueError('height', h)

            # test width
            min = camera.Width.GetMin()
            max = camera.Width.GetMax()
            if not min <= w <= max:
                raise PropertyValueError('width', w)

            # set the new height and width
            camera.Height.SetValue(h)
            camera.Width.SetValue(w)

            # test x-offset
            min = camera.OffsetX.GetMin()
            max = camera.OffsetX.GetMax()
            inc = camera.OffsetX.GetInc()
            if not min <= x <= max or x % inc != 0:
                raise PropertyValueError('x-offset', x)

            # test y-offset
            min = camera.OffsetY.GetMin()
            max = camera.OffsetY.GetMax()
            inc = camera.OffsetY.GetInc()
            if not min <= y <= max or y % inc != 0:
                raise PropertyValueError('y-offset', y)

            # all tests passed
            camera.OffsetY.SetValue(y)
            camera.OffsetX.SetValue(x)

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
