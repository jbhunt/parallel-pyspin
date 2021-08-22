import os
import yaml
import PySpin
import numpy as np
import pathlib as pl
import unittest as ut
from llpyspin.dummy import DummyCameraPointer

# constants
N_DUMMIES = 3

camera_settings_filepath = str(pl.Path(__file__).parent.joinpath('fixtures/camera-settings-data.yml'))
with open(camera_settings_filepath, 'r') as stream:
    camera_settings_data = yaml.load(stream, Loader=yaml.FullLoader)

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

def setup_camera_pointer(pointer):
    """
    Run the basic setup for camera pointers
    """

    #
    pointer.Init()

    #
    pointer.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
    pointer.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
    pointer.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_NewestOnly)

    # set the exposure
    pointer.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
    pointer.AcquisitionFrameRateEnable.SetValue(False)
    pointer.ExposureTime.SetValue(CAMERA_EXPOSURE_TARGET)

    # set the framerate
    pointer.AcquisitionFrameRateEnable.SetValue(True)
    pointer.AcquisitionFrameRate.SetValue(CAMERA_FRAMERATE_TARGET)

    # set the binsize
    pointer.BinningHorizontal.SetValue(CAMERA_BINSIZE_TARGET)
    pointer.BinningVertical.SetValue(CAMERA_BINSIZE_TARGET)

    #
    pointer.OffsetX.SetValue(CAMERA_OFFSET_TARGET)
    pointer.OffsetY.SetValue(CAMERA_OFFSET_TARGET)
    pointer.Width.SetValue(CAMERA_WIDTH_TARGET)
    pointer.Height.SetValue(CAMERA_HEIGHT_TARGET)

    #
    roi = (
        pointer.OffsetX.GetValue(),
        pointer.OffsetY.GetValue(),
        pointer.Width.GetValue(),
        pointer.Height.GetValue()
    )
    framerate = pointer.AcquisitionFrameRate.GetValue()
    exposure  = pointer.ExposureTime.GetValue()
    binsize   = (pointer.BinningHorizontal.GetValue(), pointer.BinningVertical.GetValue())

    return roi, framerate, exposure, binsize

class TestBasicCameraSetup(ut.TestCase):
    """
    """

    def setUp(self):
        """
        """

        self.cameras = [
            DummyCameraPointer() for i in range(N_DUMMIES)
        ]

        return

    def tearDown(self):
        """
        """

        for pointer in self.cameras:
            pointer.DeInit()
            del pointer

        return

    def test_camera_pointer_validity(self):
        """
        """

        for pointer in self.cameras:
            result = pointer.IsValid()
            self.assertEqual(result, True)
            del pointer

        return

    def test_pointer_property_access(self):
        """
        """

        messages = [
            f'{property} is not readable/writeable'
                for property in [
                    'Pixel format',
                    'Acquisition mode',
                    'Stream buffer handling mode',
                    'Exposure auto',
                    'Acquisition frame rate enable',
                    'Exposure time',
                    'Acquisition framerate',
                    'X offset',
                    'Y offset',
                    'Horizontal binning',
                    'Vertical binning'
                ]
        ]

        # iterate through each available camera
        for pointer in self.cameras:

            # make sure the pointer is initialized
            if not pointer.IsInitialized():
                pointer.Init()

            # collect properties in a list
            properties = [
                pointer.PixelFormat,
                pointer.AcquisitionMode,
                pointer.TLStream.StreamBufferHandlingMode,
                pointer.ExposureAuto,
                pointer.AcquisitionFrameRateEnable,
                pointer.ExposureTime,
                pointer.AcquisitionFrameRate,
                pointer.OffsetX,
                pointer.OffsetY,
                pointer.Width,
                pointer.Height,
                pointer.BinningHorizontal,
                pointer.BinningVertical
            ]

            # run tests
            for property, message in zip(properties, messages):
                self.assertEqual(property.GetAccessMode(), PySpin.RW, message)

        return

    def test_basic_camera_setup(self):
        """
        """

        # loop through each target serial number
        for pointer in self.cameras:

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
