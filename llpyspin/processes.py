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

# constants
import llpyspin.constants as c

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

class BaseProcess(Process):
    """
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
            self.started.value = 0

        try:
            if type(self.device) == str:
                camera = CAMERAS.GetBySerial(self.device)
            elif type(self.device) == int:
                camera = CAMERAS.GetByIndex(self.device)
            else:
                raise TypeError(f'The device must be a string (serial number) or integer (index) but is {type(self.device)}.')

        except TypeError:
            self.started.value = 0

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
        try:
            del camera
        except NameError:
            pass
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
            assert property in c.SUPPORTED_CAP_PROPS
        except AssertionError:
            result = False
            return result

        # try to set the property to the requested value
        try:

            # set binsize
            if property == c.CAP_PROP_BINSIZE:
                camera.BinningHorizontal.SetValue(value)
                camera.BinningVertical.SetValue(value)

            # set exposure
            elif property == c.CAP_PROP_EXPOSURE:
                camera.AcquisitionFrameRateEnable.SetValue(False)
                camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                camera.ExposureTime.SetValue(value)

            # set framerate
            elif property == c.CAP_PROP_FPS:

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

            # set buffer handling mode
            elif property == c.CAP_PROP_BUFFER_HANDLING_MODE:

                try:
                    assert property in [c.CAP_PROP_BUFFER_HANDLING_MODE_STREAMING,c.CAP_PROP_BUFFER_HANDLING_MODE_RECORDING]
                except AssertionError:
                    mode = c.CAP_PROP_BUFFER_HANDLING_MODE_DEFAULT

                tlstream_nodemap = camera.GetTLStreamNodeMap()
                handling_mode_node = PySpin.CEnumerationPtr(tlstream_nodemap.GetNode('StreamBufferHandlingMode'))
                if PySpin.IsAvailable(handling_mode_node) and PySpin.IsWritable(handling_mode_node):
                    handling_mode_entry = handling_mode_node.GetEntryByName(value)
                    if PySpin.IsAvailable(handling_mode_entry) and PySpin.IsReadable(handling_mode_entry):
                        handling_mode_node.SetIntValue(handling_mode_node.GetValue())

        except PySpin.SpinnakerException:
            result = False

        return result

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

            # TODO: figure out why the camera is still streaming after the _deacquire method is called

            if camera.IsStreaming():
                camera.EndAcquisition()

            camera.DeInit()

        except:
            result = False

        return result

class VideoStreamProcess(BaseProcess):
    """
    """

    def __init__(self, device):
        """
        """

        super().__init__(device)

        self.image = Array('i',IMAGE_SIZE)

        return

    def _acquire(self, camera):
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
            while self.acquiring.value:

                image = camera.GetNextImage()

                #
                if not image.IsIncomplete():

                    # convert the image
                    frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)

                    # store the image (critical - use lock)
                    with self.image.get_lock():
                        self.image[:] = frame.GetNDArray().flatten()

                image.Release()

        except:
            result = False

        return result

class PrimaryCameraProcess(BaseProcess):
    """
    """

    def __init__(self, device):
        """
        """

        super().__init__(device)

        return

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

    def _acquire(self, camera):
        """
        """

        result = True

        try:
            camera.BeginAcquisition()
            camera.LineSelector.SetValue(PySpin.LineSelector_Line1)
            camera.LineSource.SetValue(PySpin.LineSource_Counter0Active)

            # block while waiting for the trigger command
            triggered = self.iq.get()

            # release trigger
            if triggered:
                camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

            # abort acquisition
            else:
                return result

            # main loop
            while self.acquiring.value == 1:

                image = camera.GetNextImage()

                #
                if not image.IsIncomplete():

                    # convert the image
                    frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)

                # release the image
                image.Release()


        except PySpin.SpinnakerException:
            result = False

        return result

class SecondaryCameraProcess(BaseProcess):
    """
    """

    def __init__(self, device):
        """
        """

        super().__init__(device)

        return

    def _configure(self, camera):
        """
        """

        result = True

        try:
            camera.TriggerSource.SetValue(PySpin.TriggerSource_Line3)
            camera.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
            camera.TriggerActivation.SetValue(PySpin.TriggerActivation_AnyEdge)
            camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

        except:
            result = False

        return result

    def _deconfigure(self, camera):
        """
        """

        result = True

        try:
            camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

        except:
            result = False

        return result

    def _acquire(self, camera):
        """
        """

        result = True

        try:

            # begin aquisition
            camera.BeginAcquisition()

            # main loop
            while self.acquiring.value == 1:


                # there's a 1 second timeout for the call to GetNextImage to prevent the secondary camera
                # from blocking when video acquisition is aborted before the primary camera is triggered
                image = camera.GetNextImage(1000)

                #
                if not image.IsIncomplete():

                    # convert the image
                    frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)

                # release the image
                image.Release()


        except:
            result = False

        return result
