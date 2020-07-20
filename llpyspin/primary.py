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

# primary camera serial number
from .constants import PRIMARY_SERIALNO

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

class PrimaryCameraChildProcess(Process):
    """
    """

    def __init__(self, device=0):
        """
        """

        super().__init__()

        self.device    = device                 # device index
        self.started   = Value('i',0)           # this flag controls the main loop in the run method
        self.acquiring = Value('i',0)           # this flag controls the acquisition loop in the _start method
        self.triggered = Value('i',0)
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
            camera = CAMERAS.GetBySerial(self.serialno)
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
            self.queue.put(result)

            continue

        # clean up
        del camera
        CAMERAS.Clear()
        SYSTEM.ReleaseInstance()

        return


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
                camera.ExposureTime.SetValue(exposure)

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
                handling_mode_oldest_first = handling_mode.GetEntryByName('OldestFirst')
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

    def _configure(self, camera):
        """
        """

        result = True

        try:

            # counter 0 tracks the start of exposure
            camera.CounterSelector.SetValue(PySpin.CounterSelector_Counter0)
            camera.CounterEventSource.SetValue(PySpin.CounterEventSource_ExposureStart)
            camera.CounterTriggerSource.SetValue(PySpin.CounterTriggerSource_ExposureStart)
            camera.CounterTriggerActivation.SetValue(PySpin.CounterTriggerActivation_RisingEdge)

            # create a digital signal at half the frequency of the framerate and 50% duty cycle
            camera.LineSelector.SetValue(PySpin.LineSelector_Line2)
            camera.V3_3Enable.SetValue(True)
            camera.LineSelector.SetValue(PySpin.LineSelector_Line1)
            camera.LineSource.SetValue(PySpin.LineSource_Counter0Active)

            # set the trigger to be a software input
            camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)
            camera.TriggerSource.SetValue(PySpin.TriggerSource_Software)
            camera.TriggerOverlap.SetValue(PySpin.TriggerOverlap_Off)
            camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

        except:
            result = False

        return result

    def _activate(self, camera):
        """
        """

        result = True

        try:
            camera.BeginAcquisition()
            camera.LineSelector.SetValue(PySpin.LineSelector_Line1)
            camera.LineSource.SetValue(PySpin.LineSource_Counter0Active)

        except:
            result = False

        return result

    def _acquire(self, camera):
        """
        """

        result = True

        # double-check that the acquisition flag is set to 1
        try:
            assert self.acquiring.value == 1
        except AssertionError:
            self.acquiring.value = 1

        # wait for the trigger
        while not self.triggered.value:
            continue

        # release the trigger
        camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

        # main loop
        try:
            while self.acquiring.value == 1:

                image = camera.GetNextImage()

                #
                if not image.IsIncomplete():

                    # convert the image
                    frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)

        except:
            result = False
            break

        # reset the trigger flag
        self.triggered.value = 0

        return result

    def _deactivate(self, camera):
        """
        """

        result = True

        try:
            camera.EndAcquisition()

        except:
            result = False

        return result

    def _deconfigure(self, camera):
        """
        """

        result = True

        try:
            camera.TriggerMode.SetValue(PySpin.TriggerMode_On)
            camera.LineSelector.SetValue(PySpin.LineSelector_Line1)
            camera.LineSource.SetValue(PySpin.LineSource_FrameTriggerWait)
            camera.LineInverter.SetValue(True)

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

class PrimaryCamera():
    """
    """

    def __init__(self, serialno=None):
        """
        """

        # init and start the process
        serialno = PRIMARY_SERIALNO if serialno is None else serialno
        self._child = PrimaryCameraChildProcess(serialno)
        self._child.start()

        # check that everything is okay
        try:
            assert self._child.started.value == 1
        except AssertionError:
            logging.error('Camera instantiation failed.')
            self._child.join() # join the child process
            return

        # initialize the camera
        self._child.queue.put('initialize')
        result = self._child.queue.get()

        # read out the result
        if not result:
            logging.error('Camera initialization failed.')
            return

        # configure the camera
        self._child.queue.put('configure')
        result = self._child.queue.get()

        # read out the result
        if not result:
            logging.error('Camera configuration failed.')
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

            # set the property's value
            if hasattr(self,property):
                getattr(type(self),property).__set__(self,value)

        return

    def start(self):
        """
        start video acquisition
        """

        # check that the camera isn't acquiring
        try:
            assert self._child.acquiring.value == 0
        except AssertionError:
            logging.info('Video acquisition is already started.')
            return

        self._child.queue.put('activate')
        result = self._child.queue.get()

        if not result:
            logging.error('Failed to activate camera.')
            return

        self._child.queue.put('acquire')

        return

    def trigger(self):
        """
        trigger the master camera
        """

        # start acquisition if necessary
        if self._child.acquiring.value == 0:
            logging.warning('Video acquisition is not started. Call the start method.')
            return

        # trigger the camera
        self._child.triggered.value = 1

        return

    def stop(self):
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
        self._child.queue.put('deactivate')
        result = self._child.queue.get()

        # check result
        if not result:
            logging.warning('Failed to deactivate camera.')

        return

    def release(self):
        """
        """

        # stop acquisition if acquiring
        if self._child.acquiring.value == 1:
            loggin.info('Stopping video acquisition ...')
            self.stop()

        # deconfigure camera
        self._child.queue.put('deconfigure')
        result = self._proces.oq.get()
        if not result:
            logging.warning('Camera deconfiguration failed.')

        # de-init the camera
        self._child.queue.put('deinitialize')
        result = self._proces.oq.get()
        if not result:
            logging.warning('Camera deinitialization failed.')

        # stop and join the child process
        self._child.started.value = 0
        self._child.join()

        return

    def _set(property, value):
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

    # framerate
    @property
    def framerate(self):
        return self._framerate
    @framerate.setter
    def framerate(self, value):
        self._set(CAP_PROP_FPS,value)
        self._framerate = value

    # exposure
    @property
    def exposure(self):
        return self._exposure
    @exposure.setter
    def exposure(self, value):
        self._set(CAP_PROP_EXPOSURE,value)
        self._exposure = value

    # binsize
    @property
    def binsize(self):
        return self._binsize
    @binsize.setter
    def binsize(self, value):
        self._set(CAP_PROP_BINSIZE,value)
        self._binsize = value
