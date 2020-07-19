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
    CAP_PROP_FPS,      CAP_PROP_FPS_DEFAULT,
    CAP_PROP_BINSIZE,  CAP_PROP_BINSIZE_DEFAULT,
    CAP_PROP_EXPOSURE, CAP_PROP_EXPOSURE_DEFAULT,
    CAP_PROP_WIDTH,    CAP_PROP_WIDTH_DEFAULT,
    CAP_PROP_HEIGHT,   CAP_PROP_HEIGHT_DEFAULT
    CAP_PROP_OFFSET,   CAP_PROP_OFFSET_DEFAULT
    )

# logging setup
logging.basicConfig(format=format='%(levelname)s : %(message)s',level=logging.INFO)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

class VideoCaptureChildProcess(Process):
    """
    child process
    """

    def __init__(self, device=0):
        """
        """

        super().__init__()

        self.device    = device                 # device index
        self.started   = Value('i',0)           # this flag controls the main loop in the run method
        self.acquiring = Value('i',0)           # this flag controls the acquisition loop in the _start method
        self.queue     = Queue()                # IO queue object
        self.image     = Array('i',IMAGE_SIZE)  # this array stores the most recently acquired image

        return

    def run(self):
        """
        """

        # set the started flag to 1
        self.started.value = 1

        # create instances of the system and cameras
        SYSTEM  = PySpin.System.GetInstance()
        CAMERAS = SYSTEM.GetCameras()

        if len(CAMERAS) < 1:
            logging.warning('No cameras detected.')
            CAMERAS.Clear()
            SYSTEM.ReleaseInstance()
            return

        try:
            camera = CAMERAS.GetByIndex(self.device)
        except:
            logging.error('Camera instantiation failed.')
            CAMERAS.Clear()
            SYSTEM.ReleaseInstance()
            return

        # main loop
        while self.started.value:

            # listen for string commands
            try:
                command = self.queue.get(block=False)

            except Empty:
                continue

            # initialize the camera
            if command == 'initialize':
                result = self._initialize(camera)

            if command == 'set':
                result = self._set(camera)

            # start the acquisition
            elif command == 'start':
                result = self._start(camera)

            # stop the acquisition
            elif command == 'stop':
                result = self._stop(camera)

            # de-init the camera
            elif command == 'deinitialize':
                result = self._deinitialize(camera)

            # send the result
            self.queue.put(result)

            continue

        # clean up
        del camera
        CAMERAS.Clear()
        SYSTEM.ReleaseInstance()

        return

    def _initialize(self, camera):
        """
        """

        result = True

        try:

            #
            camera.Init()

            # set the stream bufer handling mode to oldest first
            tlstream_nodemap = camera.GetTLStreamNodeMap()
            handling_mode = PySpin.CEnumerationPtr(tlstream_nodemap.GetNode('StreamBufferHandlingMode'))
            if PySpin.IsAvailable(handling_mode) and PySpin.IsWritable(handling_mode):
                handling_mode_oldest_first = handling_mode.GetEntryByName('NewestOnly')
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
        property = self.queue.get()
        value    = self.queue.get()

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

    def _start(self, camera):
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

    def _stop(self, camera):
        """
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

class VideoCapture():
    """
    OpenCV-like video stream for a single BlackflyS camera

    notes
    -----
    This object operates like OpenCV's VideoCapture class
    """

    def __init__(self, device=0):
        """
        keywords
        --------
        device : int
            device index which specifies the camera
        """

        # init and start the process
        self._child = VideoCaptureChildProcess(device)
        self._child.start()

        # initialize the camera
        self._child.queue.put('initialize')
        result = self._child.queue.get()

        # read out the result
        if not result:
            logging.error('Camera initialization failed.')
            return

        # set the default acquisition property values
        properties = [
            CAP_PROP_FPS,
            CAP_PROP_BINSIZE,
            CAP_PROP_EXPOSURE
            ]

        values = [
            CAP_PROP_FPS_DEFAULT,
            CAP_PROP_BINSIZE_DEFAULT,
            CAP_PROP_EXPOSURE_DEFAULT
            ]

        for (property,value) in zip(properties,values):
            self._child.queue.put('set')
            self._child.queue.put(property)
            self._child.queue.put(value)
            result = self._child.queue.get()

            if not result:
                logging.warning(f'Failed to set {property} to {value}.')

        # start acquisition
        self._start()

        return

    def _start(self):
        """
        start video acquisition
        """

        # check that the camera isn't acquiring
        try:
            assert self._child.acquiring.value == 0
        except AssertionError:
            logging.info('Video acquisition is already started.')
            return

        self._child.queue.put('start')

        return

    def _stop(self):
        """
        stop video acquisition
        """

        # check that the camera is acquiring
        try:
            assert self._child.acquiring.value == 1
        except AssertionError:
            logging.info('Video acquisition is already stopped.')
            return

        # break out of the acquisition loop
        self._child.acquiring.value = 0

        # retreive the result (sent after exiting the acquisition loop)
        result = self._child.queue.get()

        if not result:
            logging.warning('Video acquisition failed.')

        # stop acquisition
        self._child.queue.put('stop')
        result = self._child.queue.get()

        # check result
        if not result:
            logging.warning('Video deacquisition failed.')

        return

    def set(property, value):
        """
        set the value of a valid acquisition property
        """

        # check that the requested property is valid
        try:
            assert property in [CAP_PROP_FPS,CAP_PROP_BINSIZE,CAP_PROP_EXPOSURE]

        except AssertionError:
            logging.warning(f'{property} is not a supported property.')
            return

        # stop the acquisition if started

        # restart acquisition or not
        restart = False

        # if acquisition is ongoing ...
        if self._child.acquiring.value:
            self._stop()
            restart = True

        # communicate with the child process
        self._child.queue.put('set')
        self._child.queue.put(property)
        self._child.queue.put(value)

        result = self._child.queue.get()

        if not result:
            logging.warning(f'Failed to set {property} to {value}.')

        # restart the acquisition if started
        if restart:
            self._start()

        return

    def isOpened(self):
        """
        returns
        -------
        result : bool
            True if streaming else False
        """

        result = True if self._child.acquiring.value == 1 else False

        return result

    def read(self):
        """
        grab the most recently acquired image
        """

        result = True

        try:

            # the lock blocks if a new image is being acquired / stored in the image attribute
            with self._child.image.get_lock():
                image = np.array(self._child.image[:],dtype=np.uint8).reshape(IMAGE_SHAPE)

        except:
            image = None
            result = False

        return (result,image)

    def release(self):
        """
        release the video stream
        """

        # stop video acquisition if ongoing
        if self._child.acquiring.value == 1:
            self._stop()

        # de-init the camera
        self._child.iq.put('deinitialize')
        result = self._child.queue.get()

        if not result:
            logging.warning('Camera de-initialization failed.')

        # break out of the main loop
        self._child.started.value = 0
        self._child.join()

        return
