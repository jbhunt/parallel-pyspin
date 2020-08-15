import queue
import logging
import numpy as np
import multiprocessing as mp

# relative imports
from ._processes  import CameraBase
from ._spinnaker  import SpinnakerMixin, spinnaker
from ._properties import PropertiesMixin, AcquisitionProperty
from ._constants  import *

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

class SecondaryCamera(CameraBase, PropertiesMixin, SpinnakerMixin):
    """
    """

    def __init__(self, device=0):
        """
        """

        try:
            super().__init__(device)

            # private attributes
            self._primed   = False
            self._nickname = '<nickname>'

            # prime the camera
            self.prime()

        except:
            self.destroy()

        return

    # overwrite the '_setall' method

    def _setall(self):
        """
        """

        self.binsize = self._binsize
        self.roi     = self._roi

        return

    # overwrite the framerate and exposure properties' setter method

    @AcquisitionProperty
    def framerate(self): return None

    @framerate.setter
    def framerate(self, value):
        logging.warning('framerate is set by the primary camera')

    @AcquisitionProperty
    def exposure(self): return None

    @exposure.setter
    def exposure(self, value):
        logging.warning('exposure is set by the primary camera')

    ### private methods ###

    @spinnaker
    def _start(self, camera):
        """
        """

        # configure the hardware trigger
        camera.TriggerSource.SetValue(PySpin.TriggerSource_Line3)
        camera.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
        camera.TriggerActivation.SetValue(PySpin.TriggerActivation_AnyEdge)
        camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

        # begin acquisition
        camera.BeginAcquisition()

        # main loop
        while self.acquiring:


            # NOTE
            # ----
            # There's a 3 second timeout for the call to GetNextImage to prevent
            # the secondary camera from blocking when video acquisition is
            # aborted before the primary camera is triggered (see below).

            try:
                image = camera.GetNextImage(3000) # timeout
            except PySpin.SpinnakerException:
                continue

            #
            if not image.IsIncomplete():

                # convert the image
                frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)

            # release the image
            image.Release()

        return

    @spinnaker
    def _stop(self, camera):
        """
        stop acquisition
        """

        # stop acquisition
        if camera.IsStreaming():
            camera.EndAcquisition()

        # deconfigure the trigger
        if camera.TriggerMode.GetValue() == PySpin.TriggerMode_On:
            camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

        return

    ### public methods ###

    def prime(self):
        """
        prime the camera for video acquisition
        """

        # check that the camera isn't acquiring
        if self.primed:
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

        # send the acquisition command
        self._iq.put(START)

        return

    def stop(self):
        """
        stop video acquisition
        """

        # check that the camera is acquiring
        try:
            assert self.primed is True
        except AssertionError:
            logging.info('video acquisition is already stopped')
            return

        # break out of the acquisition loop
        self.acquiring = False

        # retreive the result (sent after exiting the acquisition loop)
        result = self._oq.get()
        if not result:
            logging.debug('video acquisition failed')

        # stop acquisition
        self._iq.put(STOP)
        result = self._oq.get()
        if not result:
            logging.debug('video de-acquisition failed')

        return

    def release(self):
        """
        release the camera
        """

        # stop acquisition if acquiring
        if self.primed:
            logging.info('stopping video acquisition')
            self.stop()

        #
        self._iq.put(RELEASE)
        result = self._oq.get()
        if not result:
            logging.warning('camera de-initialization failed')

        # stop and join the child process
        self._destroy()

        return

    # nickname
    @property
    def nickname(self):
        return self._nickname
    @nickname.setter
    def nickname(self, value):
        self._nickname = value

    # camera ready state
    @property
    def primed(self):
        self._primed = True if self.child is not None and self.acquiring == 1 else False
        return self._primed
