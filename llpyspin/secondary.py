from llpyspin import constants
from llpyspin import capture

import queue
import logging
import numpy as np
import multiprocessing as mp

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

class SecondaryCamera(capture.VideoCaptureBase,capture.VideoCameraMixin):
    """
    """

    def __init__(self, device=0):
        """
        """

        super().__init__(device)

        # private attributes
        self._primed   = False
        self._nickname = '<nickname>'

        # prime the camera
        self.prime()

        return

    ### special methods ###

    def _start(self, camera):
        """
        """

        try:

            # configure the hardware trigger
            camera.TriggerSource.SetValue(PySpin.TriggerSource_Line3)
            camera.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
            camera.TriggerActivation.SetValue(PySpin.TriggerActivation_AnyEdge)
            camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

            # begin acquisition
            camera.BeginAcquisition()

            # main loop
            while self.acquiring.value == 1:


                ### NOTE ###
                #
                # There's a 3 second timeout for the call to GetNextImage to prevent
                # the secondary camera from blocking when video acquisition is
                # aborted before the primary camera is triggered (see below).
                #

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

            result = constants.SUCCESS

        except PySpin.SpinnakerException:
            result = constants.FAILURE

        return result

    def _stop(self, camera):
        """
        stop acquisition
        """

        result = True

        try:

            # stop acquisition
            if camera.IsStreaming():
                camera.EndAcquisition()

            # deconfigure the trigger
            if camera.TriggerMode.GetValue() == PySpin.TriggerMode_On:
                camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

            result = constants.SUCCESS

        except:
            result = constants.FAILURE

        return result

    ### public methods ###

    def prime(self):
        """
        prime the camera for video acquisition
        """

        # check that the camera isn't acquiring
        try:
            assert self.primed is False
        except AssertionError:
            logging.info('Video acquisition is already started.')
            return

        # intitialize the child process
        self._initializeChild()

        # attempt to initialize the camera
        attempt   = 0 # attempt counter
        threshold = 5 # max number of attempts allowed
        result    = constants.FAILURE # default result

        while not result:

            # check attempt counter
            attempt += 1
            if attempt > threshold:
                logging.error(f'Failed to initialize the camera with {attempt} attempts. Destroying child.')
                self._destroyChild()
                return

            # attempt to initialize the camera
            self._iq.put(constants.INITIALIZE)
            result = self._.oq.get()

            # restart the child process
            if not result:
                logging.warning(f'Camera initialization failed (attempt number {attempt}). Restarting child.')
                self._destroyChild()
                self._initializeChild()
                continue

        # set the acquisition properties
        self._setAllProperties()

        # set the acquiring flag to 1
        self._acquiring.value = 1

        # send the acquisition command
        self._iq.put(constants.START)

        return

    def stop(self):
        """
        stop video acquisition
        """

        # check that the camera is acquiring
        try:
            assert self.primed is True
        except AssertionError:
            logging.info('Video acquisition is already stopped.')
            return

        # break out of the acquisition loop
        self.acquiring = 0

        # retreive the result (sent after exiting the acquisition loop)
        result = self._oq.get()
        if not result:
            logging.warning('Video acquisition failed.')

        # stop acquisition
        self._iq.put(constants.STOP)
        result = self._oq.get()
        if not result:
            logging.warning('Video de-acquisition failed.')

        return
