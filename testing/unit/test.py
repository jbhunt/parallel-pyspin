import os
import PySpin
import numpy as np
import unittest as ut
from llpyspin.dummy import DummyCameraPointer
from llpyspin.primary import PrimaryCamera
from llpyspin.secondary import SecondaryCamera
from llpyspin.streaming import VideoStream
from llpyspin.recording import SpinnakerVideoWriter, OpenCVVideoWriter, FFmpegVideoWriter

# environment variables
USER_HOME_DIRECTORY  = os.environ['HOME']
DEVICE_INDEX_NUMBER  = os.environ['DEVICE_INDEX_NUMBER']
DEVICE_SERIAL_NUMBER = os.environ['DEVICE_INDEX_NUMBER']

def execute_basic_camera_setup(camera):
    """
    """

    #
    camera.Init()

    #
    camera.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
    camera.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
    camera.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_NewestOnly)

    # set the exposure
    camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
    camera.AcquisitionFrameRateEnable.SetValue(False)
    camera.ExposureTime.SetValue(3000)

    # set the framerate
    camera.AcquisitionFrameRateEnable.SetValue(True)
    camera.AcquisitionFrameRate.SetValue(30)

    # set the binsize
    camera.BinningHorizontal.SetValue(2)
    camera.BinningVertical.SetValue(2)

    #
    x = camera.OffsetX.GetValue()
    y = camera.OffsetY.GetValue()
    w = camera.Width.GetValue()
    h = camera.Height.GetValue()

    #
    roi = (x, y, w, h)
    framerate = int(np.ceil(camera.AcquisitionFrameRate.GetValue()))
    exposure  = int(np.ceil(camera.ExposureTime.GetValue()))
    binsize   = (camera.BinningHorizontal.GetValue(), camera.BinningVertical.GetValue())

    return roi, framerate, exposure, binsize

class TestCameraInitProcedure(ut.TestCase):
    """
    """

    def setUp(self):
        return

    def _test_camera_init_using_dummy_device(self):
        """
        """

        # instantiate the camera
        camera = DummyCameraPointer()

        # run the basic setup
        execute_basic_camera_setup(camera)

        return

    def test_camera_init_using_device_serialno(self):
        """
        """

        # force into a string
        if not isinstance(DEVICE_SERIAL_NUMBER, str):
            serialno = str(DEVICE_SERIAL_NUMBER)
        else:
            serialno = DEVICE_SERIAL_NUMBER

        # instantiate the camera
        system = PySpin.System.GetInstance()
        cameras = system.GetCameras()
        camera = cameras.GetBySerial(serialno)

        # run the basic setup
        execute_basic_camera_setup(camera)

        return

    def _test_camera_init_using_device_index(self, index=0):
        """
        """

        return

if __name__ == '__main__':
    ut.main()
