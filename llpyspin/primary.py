# imports
import queue
import ctypes
import logging
import numpy as np
import multiprocessing as mp

# relative imports
from ._processes  import CameraBase
from ._spinnaker  import SpinnakerMixin
from ._properties import PropertiesMixin

#
from . import recording

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

class PrimaryCamera(CameraBase, PropertiesMixin, SpinnakerMixin):
    """
    """

    def __init__(self, device=0):
        """
        """

        super().__init__(device)

        # private attributes
        self._trigger  = mp.Event()
        self._filename = mp.Value(ctypes.c_char_p, None)
        self._nickname = 'primary-camera' # camera nickname

        logging.info('creating primary camera')

        # spawn the child process
        self._spawn()

        # attempt to initialize the camera
        self._iq.put('initialize')
        if self._result == False:
            logging.error(f'camera initialization failed')
            return

        self.framerate = 60
        self.exposure  = 1500
        self.binsize   = None

        return

    ### private methods ###

    def _initialize(self, camera):
        """
        """

        # init the camera
        camera.Init()

        # pixel format
        camera.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)

        # acquisition mode
        camera.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)

        # stream buffer handling mode
        camera.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_OldestFirst)

        # disable auto exposure
        camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)

        return

    def _start(self, camera):
        """
        """

        # prepare for the recording
        args = self._iq.get()
        writer = recording.VideoWriter(*args)

        # create a counter that tracks the onset sensor exposure
        camera.CounterSelector.SetValue(PySpin.CounterSelector_Counter0)
        camera.CounterEventSource.SetValue(PySpin.CounterEventSource_ExposureStart)
        camera.CounterTriggerSource.SetValue(PySpin.CounterTriggerSource_ExposureStart)
        camera.CounterTriggerActivation.SetValue(PySpin.CounterTriggerActivation_RisingEdge)

        # create a digital signal whose PWD is determined by the counter
        camera.LineSelector.SetValue(PySpin.LineSelector_Line2)
        camera.V3_3Enable.SetValue(True)
        camera.LineSelector.SetValue(PySpin.LineSelector_Line1)
        camera.LineSource.SetValue(PySpin.LineSource_Counter0Active)

        # tell the camera to wait for a software trigger
        # NOTE : In reality the camera is triggered by un-setting the trigger mode (see below).
        camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)
        camera.TriggerSource.SetValue(PySpin.TriggerSource_Software)
        camera.TriggerOverlap.SetValue(PySpin.TriggerOverlap_Off)
        camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

        # begin acquisition
        camera.BeginAcquisition()

        # wait for the trigger
        self._trigger.wait() # returns the state of the internal flag

        # unset the trigger mode
        camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

        txtfile = open('/home/polegpolskylab/Desktop/cam1.txt', 'w')

        # main loop
        while self.acquiring:

            try:
                image = camera.GetNextImage(1)
            except PySpin.SpinnakerException:
                continue

            #
            if not image.IsIncomplete():

                # convert the image
                frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
                txtfile.write(str(frame.GetTimeStamp()) + '\n')

                # save the result
                writer.write(image)

            # release the image
            image.Release()

        # stop acquisition by resetting the trigger mode
        camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

        # empty out the transfer queue buffer
        while True:
            try:
                image = camera.GetNextImage(1000)
            except PySpin.SpinnakerException:
                break

        #
        writer.close()

        return

    def _stop(self, camera):
        """
        stop acquisition
        """

        # reset the trigger
        if self._trigger.is_set():
            self._trigger.clear()

        # stop acquisition
        if camera.IsStreaming():
            camera.EndAcquisition()

        # deconfigure the trigger
        camera.TriggerMode.SetValue(PySpin.TriggerMode_On)
        camera.LineSelector.SetValue(PySpin.LineSelector_Line1)
        camera.LineSource.SetValue(PySpin.LineSource_FrameTriggerWait)
        camera.LineInverter.SetValue(True)

        return

    ### public methods ###

    def prime(self, filename):
        """
        prime the camera for video recording

        keywords
        --------
        filename : str
            a filename for the video (includeing the ".avi" file extension)
        """

        # make sure the camera isn't started
        if self.primed == True:
            logging.info('camera is already primed')
            return

        if not filename.endswith('.avi'):
            raise ValueError('filename string must end with ".avi" extension')

        # set the acquiring flag to 1
        self.acquiring = True

        # send command to start acquisition
        self._iq.put('start')

        # overwrite the current filename
        self.filename = filename

        #
        args = [filename, None, self.framerate, (self.roi[2:])]
        self._iq.put(args)

        # engage the acquisition lock
        self.locked = True

        return

    def trigger(self):
        """
        trigger the camera
        """

        # start acquisition if necessary
        if self.primed == False:
            logging.info('camera is not primed')
            return

        self._trigger.set()

        return

    def stop(self):
        """
        stop video acquisition
        """

        # check that the camera is acquiring
        if self.acquiring == False:
            logging.info('video acquisition is already stopped')
            return

        logging.info('stopping video acquisition')

        # break out of the acquisition loop
        self.acquiring = False

        # abort the acquisition if necessary
        if not self._trigger.is_set():
            self._trigger.set() # release the trigger

        # retreive the result (sent after exiting the acquisition loop)
        if self._result == False:
            logging.warning('video acquisition failed')

        # stop acquisition
        self._iq.put('stop')
        if self._result == False:
            logging.warning('video de-acquisition failed')

        # release the acquisition lock
        self.locked = False

        return

    def release(self):
        """
        release the camera
        """

        # stop acquisition if acquiring
        if self.primed == True:
            self.stop()

        #
        self._iq.put('release')
        if self._result == False:
            logging.warning('camera de-initialization failed')

        # stop and join the child process
        self._kill()

        return

    # camera ready state
    @property
    def primed(self):
        return True if self._child is not None and self.acquiring == 1 else False

    # camera trigger state
    @property
    def triggered(self):
        return True if self._trigger.is_set() else False

    # filename
    @property
    def filename(self):
        return self._filename.value.decode()

    @filename.setter
    def filename(self, value):
        if type(value) is not str:
            raise ValueError('filename must be a string')
        self._filename.value = value.encode()

    # nickname
    @property
    def nickname(self):
        return self._nickname
    @nickname.setter
    def nickname(self, value):
        self._nickname = value
