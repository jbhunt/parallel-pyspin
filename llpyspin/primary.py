# imports
import queue
import logging
import numpy as np
import multiprocessing as mp

# relative imports
from ._processes  import CameraBase
from ._spinnaker  import SpinnakerMixin, spinnaker
from ._properties import PropertiesMixin
from ._constants  import *

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
        self._lock      = mp.Lock()        # acquisition lock
        self._trigger   = mp.Event()
        self._nickname  = 'primary-camera' # camera nickname

        # prime the camera
        self.prime()

        return

    ### special methods ###

    @spinnaker
    def _start(self, camera):
        """
        """

        # engage the acquisition lock
        self._lock.acquire()

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

        # main loop
        while self.acquiring:

            image = camera.GetNextImage()

            #
            if not image.IsIncomplete():

                # convert the image
                frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)

            # release the image
            image.Release()

        # release the acquisition lock
        self._lock.release()

        return

    @spinnaker
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

    def prime(self):
        """
        prime the camera for video acquisition
        """

        # make sure the camera isn't started
        if self.primed is True:
            logging.info('camera is already primed')
            return

        # intitialize the child process
        if self.child is None:
            self._create()

        # attempt to initialize the camera
        self._iq.put(INITIALIZE)
        result = self._oq.get()
        if not result:
            logging.error(f'camera initialization failed')
            return

        # set the acquisition properties
        self._setall()

        # set the acquiring flag to 1
        self.acquiring = True

        # send command to start acquisition
        self._iq.put(START)

        return

    def trigger(self):
        """
        trigger the camera
        """

        # start acquisition if necessary
        if not self.primed:
            logging.warning('camera is not primed')
            return

        self._trigger.set()

        return

    def stop(self):
        """
        stop video acquisition
        """

        logging.info('stopping video acquisition')

        # check that the camera is acquiring
        if not self.acquiring:
            logging.info('video acquisition is already stopped')
            return

        # break out of the acquisition loop
        self.acquiring = False

        # abort the acquisition if necessary
        if not self._trigger.is_set():
            self._trigger.set() # release the trigger

        # retreive the result (sent after exiting the acquisition loop)
        result = self._oq.get()
        if not result:
            logging.warning('video acquisition failed')

        # stop acquisition
        self._iq.put(STOP)
        result = self._oq.get()
        if not result:
            logging.warning('video de-acquisition failed')

        return

    def release(self):
        """
        release the camera
        """

        # stop acquisition if acquiring
        if self.primed:
            self.stop()

        #
        self._iq.put(RELEASE)
        result = self._oq.get()
        if not result:
            logging.warning('camera de-initialization failed')

        # stop and join the child process
        self._destroy()

        return

    # camera ready state
    @property
    def primed(self):
        return True if self.child is not None and self.acquiring == 1 else False

    # camera trigger state
    @property
    def triggered(self):
        return True if self._trigger.is_set() else False

    # nickname
    @property
    def nickname(self):
        return self._nickname
    @nickname.setter
    def nickname(self, value):
        self._nickname = value
