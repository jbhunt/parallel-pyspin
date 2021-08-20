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

camera_settings_filepath = str(pl.Path(__file__).parent.joinpath('fixtures/camera-settings-data.yml'))
with open(camera_settings_filepath, 'r') as stream:
    camera_settings_data = yaml.load(stream, Loader=yaml.FullLoader)

# serial numbers
CAMERA_SERIAL_NUMBERS      = camera_settings_data['camera_serial_numbers']

# target values for the acquisition properties
CAMERA_FRAMERATE_TARGET    = camera_settings_data['camera_settings_data']['framerate']['target']
CAMERA_BINSIZE_TARGET      = camera_settings_data['camera_settings_data']['binsize']['target']
CAMERA_WIDTH_TARGET        = camera_settings_data['camera_settings_data']['width']['target']
CAMERA_HEIGHT_TARGET       = camera_settings_data['camera_settings_data']['height']['target']
CAMERA_EXPOSURE_TARGET     = camera_settings_data['camera_settings_data']['exposure']['target']
CAMERA_OFFSET_TARGET       = camera_settings_data['camera_settings_data']['offset']['target']

# tolerance for the values of the acquisition properties
CAMERA_FRAMERATE_TOLERANCE = camera_settings_data['camera_settings_data']['framerate']['tolerance']
CAMERA_EXPOSURE_TOLERANCE  = camera_settings_data['camera_settings_data']['exposure']['tolerance']

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
    camera.ExposureTime.SetValue(CAMERA_EXPOSURE_TARGET)

    # set the framerate
    camera.AcquisitionFrameRateEnable.SetValue(True)
    camera.AcquisitionFrameRate.SetValue(CAMERA_FRAMERATE_TARGET)

    # set the binsize
    camera.BinningHorizontal.SetValue(CAMERA_BINSIZE_TARGET)
    camera.BinningVertical.SetValue(CAMERA_BINSIZE_TARGET)

    #
    camera.OffsetX.SetValue(CAMERA_OFFSET_TARGET)
    camera.OffsetY.SetValue(CAMERA_OFFSET_TARGET)
    camera.Width.SetValue(CAMERA_WIDTH_TARGET)
    camera.Height.SetValue(CAMERA_HEIGHT_TARGET)

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

    def setUp(self):
        """
        """

        self.system = PySpin.System.GetInstance()
        self.cameras = self.system.GetCameras()

        return

    def tearDown(self):
        """
        """

        self.cameras.Clear()
        del self.cameras
        self.system.ReleaseInstance()
        del self.system

        return

    def test_camera_pointer_validity(self):
        """
        """

        for serialno in CAMERA_SERIAL_NUMBERS:
            pointer = self.cameras.GetBySerial(str(serialno))
            result = pointer.IsValid()
            self.assertEqual(result, True)
            del pointer

        return

    def test_basic_camera_setup(self):
        """
        """

        # loop through each target serial number
        for serialno in CAMERA_SERIAL_NUMBERS:

            # instantiate the pointer
            pointer = self.cameras.GetBySerial(str(serialno))

            # run the basic setup and get the results
            roi, framerate, exposure, binsize = setup_camera_pointer(pointer)

            # remove the reference to the camera pointer object
            pointer.DeInit()
            del pointer

            # check the results
            x, y, w, h = roi
            test_property_names = [
                'width',
                'height',
                'offset',
                'offset',
                'binsize',
                'binsize',
                'exposure',
                'framerate'
            ]
            test_property_values = [
                CAMERA_WIDTH_TARGET,
                CAMERA_HEIGHT_TARGET,
                CAMERA_OFFSET_TARGET,
                CAMERA_OFFSET_TARGET,
                CAMERA_BINSIZE_TARGET,
                CAMERA_BINSIZE_TARGET,
                CAMERA_EXPOSURE_TARGET,
                CAMERA_FRAMERATE_TARGET
            ]
            actual_property_values = [w, h, x, y, binsize[0], binsize[1], exposure, framerate]

            # pack test data
            iterable = zip(
                test_property_names,
                test_property_values,
                actual_property_values
            )

            # run tests
            for name, target, actual in iterable:
                if name == 'exposure':
                    message = f'Actual exposure time of {actual} us is not in the range: {target} +/- {CAMERA_EXPOSURE_TOLERANCE} us'
                    self.assertTrue(target - CAMERA_EXPOSURE_TOLERANCE <= actual <= target + CAMERA_EXPOSURE_TOLERANCE, message)
                elif name == 'framerate':
                    message = f'Actual framerate of {actual} fps is not in the range: {target} +/- {CAMERA_FRAMERATE_TOLERANCE} fps'
                    self.assertTrue(target - CAMERA_FRAMERATE_TOLERANCE <= actual <= target + CAMERA_FRAMERATE_TOLERANCE, message)
                else:
                    message = f'Actual {name} of {actual} is not equal to the target value: {target}'
                    self.assertAlmostEqual(target, actual, target)

        return

if __name__ == '__main__':
    ut.main()
