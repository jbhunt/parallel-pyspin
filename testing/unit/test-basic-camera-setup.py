import os
import yaml
import PySpin
import numpy as np
import pathlib as pl
import unittest as ut
from llpyspin.dummy import DummyCameraPointer
from llpyspin.primary import PrimaryCamera
from llpyspin.secondary import SecondaryCamera
from llpyspin.streaming import VideoStream
from llpyspin.recording import SpinnakerVideoWriter, OpenCVVideoWriter, FFmpegVideoWriter

# constants
USER_HOME_PATH = os.environ['HOME']

camera_settings_filepath = str(pl.Path(__file__).parent.joinpath('fixtures/cameras.yml'))
with open(camera_settings_filepath, 'r') as stream:
    camera_settings_data = yaml.load(stream, Loader=yaml.FullLoader)

TESTING_CAMERA_FRAMERATE = camera_settings_data['testing_property_values']['framerate']
TESTING_CAMERA_BINSIZE   = camera_settings_data['testing_property_values']['binsize']
TESTING_CAMERA_WIDTH     = camera_settings_data['testing_property_values']['width']
TESTING_CAMERA_HEIGHT    = camera_settings_data['testing_property_values']['height']
TESTING_CAMERA_EXPOSURE  = camera_settings_data['testing_property_values']['exposure']
TESTING_CAMERA_OFFSET    = camera_settings_data['testing_property_values']['offset']

CAMERA_SERIAL_NUMBERS    = camera_settings_data['camera_serial_numbers']

def setup_camera_pointer(camera):
    """
    Run the basic setup for camera pointers
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
    camera.ExposureTime.SetValue(TESTING_CAMERA_EXPOSURE)

    # set the framerate
    camera.AcquisitionFrameRateEnable.SetValue(True)
    camera.AcquisitionFrameRate.SetValue(TESTING_CAMERA_FRAMERATE)

    # set the binsize
    camera.BinningHorizontal.SetValue(TESTING_CAMERA_BINSIZE)
    camera.BinningVertical.SetValue(TESTING_CAMERA_BINSIZE)

    #
    camera.OffsetX.SetValue(TESTING_CAMERA_OFFSET)
    camera.OffsetY.SetValue(TESTING_CAMERA_OFFSET)
    camera.Width.SetValue(TESTING_CAMERA_WIDTH)
    camera.Height.SetValue(TESTING_CAMERA_HEIGHT)

    #
    roi = (
        camera.OffsetX.GetValue(),
        camera.OffsetY.GetValue(),
        camera.Width.GetValue(),
        camera.Height.GetValue()
    )
    framerate = camera.AcquisitionFrameRate.GetValue()
    exposure  = camera.ExposureTime.GetValue()
    binsize   = (camera.BinningHorizontal.GetValue(), camera.BinningVertical.GetValue())

    return roi, framerate, exposure, binsize

class TestBasicCameraSetup(ut.TestCase):
    """
    """

    def test_setup_using_dummy_pointer(self):
        """
        """

        # instantiate the camera
        pointer = DummyCameraPointer()

        # run the basic setup
        roi, framerate, exposure, binsize = setup_camera_pointer(pointer)

        # check the results
        x, y, w, h = roi
        test_property_values = [
            TESTING_CAMERA_WIDTH,
            TESTING_CAMERA_HEIGHT,
            TESTING_CAMERA_OFFSET,
            TESTING_CAMERA_OFFSET,
            TESTING_CAMERA_BINSIZE,
            TESTING_CAMERA_BINSIZE,
            TESTING_CAMERA_EXPOSURE,
            TESTING_CAMERA_FRAMERATE
        ]
        for test, actual in zip(test_property_values, [w, h, x, y, binsize[0], binsize[1], exposure, framerate]):
            self.assertAlmostEqual(test, actual)

        return

    def test_setup_using_actual_pointer(self):
        """
        """

        # instantiate the pointer
        system = PySpin.System.GetInstance()
        cameras = system.GetCameras()

        # loop through each target serial number
        for serialno in CAMERA_SERIAL_NUMBERS:

            # instantiate the pointer
            pointer = cameras.GetBySerial(str(serialno))

            # run the basic setup and get the results
            roi, framerate, exposure, binsize = setup_camera_pointer(pointer)

            # check the results
            x, y, w, h = roi
            test_property_values = [
                TESTING_CAMERA_WIDTH,
                TESTING_CAMERA_HEIGHT,
                TESTING_CAMERA_OFFSET,
                TESTING_CAMERA_OFFSET,
                TESTING_CAMERA_BINSIZE,
                TESTING_CAMERA_BINSIZE,
                TESTING_CAMERA_EXPOSURE,
                TESTING_CAMERA_FRAMERATE
            ]
            for test, actual in zip(test_property_values, [w, h, x, y, binsize[0], binsize[1], exposure, framerate]):
                self.assertAlmostEqual(test, actual)

            pointer.DeInit()
            del pointer

        cameras.Clear()
        del cameras
        system.ReleaseInstance()
        del system

        return

if __name__ == '__main__':
    ut.main()
