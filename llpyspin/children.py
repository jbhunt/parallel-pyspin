# imports
import os
import logging
import numpy as np
from queue import Empty
from multiprocessing import Array
from multiprocessing import Value
from multiprocessing import Queue
from multiprocessing import Process
from multiprocessing import Lock

# relative imports

# image properties
from .constants import (
    IMAGE_SIZE,
    IMAGE_SHAPE,
    IMAGE_WIDTH,
    IMAGE_HEIGHT
    )

# default acquisition property key and value pairs
from .constants import (
    CAP_PROP_FPS,
    CAP_PROP_FPS_DEFAULT,
    CAP_PROP_BINSIZE,
    CAP_PROP_BINSIZE_DEFAULT,
    CAP_PROP_EXPOSURE,
    CAP_PROP_EXPOSURE_DEFAULT,
    CAP_PROP_WIDTH,
    CAP_PROP_WIDTH_DEFAULT,
    CAP_PROP_HEIGHT,
    CAP_PROP_HEIGHT_DEFAULT,
    CAP_PROP_OFFSET,
    CAP_PROP_OFFSET_DEFAULT
    )

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

class ChildProcess(Process):
    """
    child process
    """

    def __init__(self, device):
        """
        """

        super().__init__()

        self.device    = device                 # this is either an index (int) or serial number (str)
        self.started   = Value('i',0)           # this flag controls the main loop in the run method
        self.acquiring = Value('i',0)           # this flag controls the acquisition loop in the _start method
        self.iq        = Queue()                # input Queue
        self.oq        = Queue()                # output Queue

        return

    def run(self):
        """
        """

        # set the started flag to 1
        self.started.value = 1

        # create instances of the system and cameras
        SYSTEM  = PySpin.System.GetInstance()
        CAMERAS = SYSTEM.GetCameras()

        try:
            assert len(CAMERAS) >= 1
        except AssertionError:
            logging.warning('No cameras detected.')
        finally:
            CAMERAS.Clear()
            SYSTEM.ReleaseInstance()
            return

            # TODO : join the process

        try:
            if type(self.device) == str:
                camera = CAMERAS.GetBySerial(self.device)
            elif type(self.device) == int:
                camera = CAMERAS.GetByIndex(self.device)
            else:
                raise ValueError(f'The device must be a string (serial number) or integer (index) but is {type(self.device)}.')

        except:
            logging.error('Camera instantiation failed.')

        finally:
            CAMERAS.Clear()
            SYSTEM.ReleaseInstance()
            return

        # main loop
        while self.started.value:

            # listen for string commands
            try:
                command = self.iq.get(block=False)

            except Empty:
                continue

            # set a valid acquisition property
            if command == 'set':
                result = self._set(camera)

            # initialize the camera
            elif command == 'initialize':
                result = self._initialize(camera)

            # setup the camera's trigger mechanism
            elif command == 'configure':
                result = self._configure(camera)

            # start the acquisition
            elif command == 'acquire':
                result = self._acquire(camera)

            # reset the camera's trigger mechanism
            elif command == 'deconfigure':
                result = self._deacquire(camera)

            # de-init the camera
            elif command == 'deinitialize':
                result = self._deinitialize(camera)

            # send the result
            self.oq.put(result)

            continue

        # clean up
        del camera
        CAMERAS.Clear()
        SYSTEM.ReleaseInstance()

        return

    def _initialize(self, camera, mode='NewestOnly'):
        """
        keywords
        --------
        camera
            instance of a camera object
        mode
            stream buffer handling mode
        """

        # check that the mode argument is a valid stream buffer handling mode
        try:
            assert mode in ['NewestOnly','MostRecentFirst']
        except AssertionError:
            result = False
            return result

        result = True

        try:

            #
            camera.Init()

            # set the stream bufer handling mode to oldest first
            tlstream_nodemap = camera.GetTLStreamNodeMap()
            handling_mode = PySpin.CEnumerationPtr(tlstream_nodemap.GetNode('StreamBufferHandlingMode'))
            if PySpin.IsAvailable(handling_mode) and PySpin.IsWritable(handling_mode):
                handling_mode_oldest_first = handling_mode.GetEntryByName(mode)
                if PySpin.IsAvailable(handling_mode_oldest_first) and PySpin.IsReadable(handling_mode_oldest_first):
                    handling_mode.SetIntValue(handling_mode_oldest_first.GetValue())

            # set the acquisition mode to continuous
            nodemap = camera.GetNodeMap()
            node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
            if PySpin.IsAvailable(node_acquisition_mode) and PySpin.IsWritable(node_acquisition_mode):
                acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
                if PySpin.IsAvailable(acquisition_mode_continuous) and PySpin.IsReadable(acquisition_mode_continuous):
                    node_acquisition_mode.SetIntValue(acquisition_mode_continuous.GetValue())

            # set the pixel format to mono 8
            node_pixel_format = PySpin.CEnumerationPtr(nodemap.GetNode('PixelFormat'))
            if PySpin.IsAvailable(node_pixel_format) and PySpin.IsWritable(node_pixel_format):
                pixel_format_mono8 = PySpin.CEnumEntryPtr(node_pixel_format.GetEntryByName('Mono8'))
                if PySpin.IsAvailable(pixel_format_mono8) and PySpin.IsReadable(pixel_format_mono8):
                    node_pixel_format.SetIntValue(pixel_format_mono8.GetValue())

        except:
            result = False

        return result

    def _set(self, camera):
        """
        """

        result = True

        # get the property and its requested value
        property = self.iq.get()
        value    = self.iq.get()

        # check that the property is valid
        try:
            assert property in [CAP_PROP_FPS,CAP_PROP_BINSIZE,CAP_PROP_EXPOSURE]
        except:
            result = False
            return result

        # try to set the property to the requested value
        try:

            # set binsize
            if property == 'binsize':
                camera.BinningHorizontal.SetValue(value)
                camera.BinningVertical.SetValue(value)

            # set exposure
            elif property == 'exposure':
                camera.AcquisitionFrameRateEnable.SetValue(False)
                camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                camera.ExposureTime.SetValue(value)

            # set framerate
            elif property == 'framerate':

                # enable framerate customization
                camera.AcquisitionFrameRateEnable.SetValue(True)

                # maximum framerate
                threshold = np.floor(camera.AcquisitionFrameRate.GetMax())

                # requested framerate is greater than the maximum framerate
                if value > threshold:
                    camera.AcquisitionFrameRate.SetValue(threshold)

                # requested framerate is less than the maximum framerate
                else:
                    camera.AcquisitionFrameRate.SetValue(value)

        except PySpin.SpinnakerException:
            result = False

        return result

    def _acquire(self, camera):
        """
        start video acquisition

        notes
        -----
        This method will be unique for each subclass so it is defined only in name here
        """

        return True

    def _deacquire(self, camera):
        """
        stop acquisition
        """

        result = True

        try:
            camera.EndAcquisition()

        except:
            result = False

        return result

    def _deinitialize(self, camera):
        """
        """

        result = True

        try:
            camera.DeInit()

        except:
            result = False

        return result

class VideoStreamChildProcess(ChildProcess):
    """
    """

    def __init__(self, device):
        """
        """

        super().__init__(device)

        self.image = Array('i',IMAGE_SIZE)

        return

    def _acquire(self):
        """
        """

        result = True

        # begin acquisition
        try:
            camera.BeginAcquisition()
        except:
            result = False
            return result

        # double-check that the acquisition flag is set to 1
        try:
            assert self.acquiring.value == 1
        except AssertionError:
            self.acquiring.value = 1

        # main loop
        try:
            while self.acquiring.value == 1:

                image = camera.GetNextImage()

                #
                if not image.IsIncomplete():

                    # convert the image
                    frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)

                    # store the image (critical - use lock)
                    with self.image.get_lock():
                        self.image[:] = frame.GetNDArray().flatten()

        except:
            result = False

        return result
