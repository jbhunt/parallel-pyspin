import types
import logging

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

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
    the camera object as an argument.
    """

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

    def _get(self, camera):
        """
        retreive the value of an acquisition property
        """

        (property, feature) = self._iq.get()

        if property == 'framerate':

            if feature == 'maximum':
                value = camera.AcquisitionFrameRate.GetMax()
            if feature == 'minimum':
                value = camera.AcquisitionFrameRate.GetMin()
            if feature == 'current':
                value = camera.AcquisitionFrameRate.GetValue()

        elif property == 'width':

            if feature == 'maximum':
                value = camera.Width.GetMax()
            if feature == 'minimum':
                value = camera.Width.GetMin()
            if feature == 'current':
                value = camera.Width.GetValue()

        elif property == 'height':

            if feature == 'maximum':
                value = camera.Height.GetMax()
            if feature == 'minimum':
                value = camera.Height.GetMin()
            if feature == 'current':
                value = camera.Height.GetValue()

        elif property == 'offset':

            if feature == 'current':
                value = (camera.OffsetX.GetValue(), camera.OffsetY.GetValue())
            if feature == 'maximum':
                value = (camera.OffsetX.GetMax(), camera.OffsetY.GetMax())

        else:
            value = None

        # put the requested value in the output queue
        self._oq.put(value)

        return

    def _set(self, camera):
        """
        set the value of an acquisition property
        """

        # retreive the property id and requested value
        (property, value) = self._iq.get()

        # framerate
        if property == 'framerate':

            # test the requested value
            min  = camera.AcquisitionFrameRate.GetMin()
            max  = camera.AcquisitionFrameRate.GetMax()
            if not min <= value <= max:
                raise PySpin.SpinnakerException()

            # test passed
            camera.AcquisitionFrameRateEnable.SetValue(True)
            camera.AcquisitionFrameRate.SetValue(value)

        # exposure
        if property == 'exposure':

            #
            min = camera.ExposureTime.GetMin()
            max = camera.ExposureTime.GetMax()
            if not min <= value <= max:
                raise PySpin.SpinnakerException()

            #
            camera.AcquisitionFrameRateEnable.SetValue(False)
            camera.ExposureTime.SetValue(value)
            camera.AcquisitionFrameRateEnable.SetValue(True)

        # binsize
        if property == 'binsize':

            #
            min = camera.BinningVertical.GetMin()
            max = camera.BinningVertical.GetMax()
            if not min <= value <= max:
                raise PySpin.SpinnakerException()

            # TODO : check that the value is a valid increment of each bin axis

            #
            camera.BinningHorizontal.SetValue(value)
            camera.BinningVertical.SetValue(value)

        # region of interest
        if property == 'roi':

            # unpack the ROI parameters
            (y, x, h, w) = value # TODO : change the order of parameters to x, y, w, h

            #
            test1 = (x + w) <= (camera.Width.GetMax() + camera.OffsetX.GetValue())
            test2 = (y + h) <= (camera.Height.GetMax() + camera.OffsetY.GetValue())
            test3 = (x % camera.OffsetX.GetInc() == 0) and (y % camera.OffsetY.GetInc() == 0)
            if False in [test1, test2, test3]:
                raise PySpin.SpinnakerException()

            # set the new roi
            camera.Height.SetValue(h)
            camera.Width.SetValue(w)
            camera.OffsetY.SetValue(y)
            camera.OffsetX.SetValue(x)

        # shape of the video frame
        if property == 'shape':
            (h, w) = value
            camera.Height.SetValue(h)
            camera.Width.SetValue(w)

        # offset of the video frame
        if property == 'offset':
            (y, x) = value
            camera.OffsetY.SetValue(y)
            camera.OffsetX.SetValue(x)

        return

    def _start(self, camera):
        camera.BeginAcquisition()

    def _stop(self, camera):
        camera.EndAcquisition()

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
