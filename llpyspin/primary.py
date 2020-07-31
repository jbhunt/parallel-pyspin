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

class PrimaryCamera(capture.VideoCaptureBase,capture.VideoCameraMixin):
    """
    """

    def __init__(self, device=0):
        """
        """

        super().__init__(device)

        # private attributes
        self._triggered = False # camera trigger state
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

            # configure the trigger

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

            # activate the counter - shouldn't have to do this again but you never know
            # camera.LineSelector.SetValue(PySpin.LineSelector_Line1)
            # camera.LineSource.SetValue(PySpin.LineSource_Counter0Active)

            # block while waiting for the trigger command
            triggered = self.iq.get()

            # un-set the trigger mode (in effect trigger the camera)
            if triggered:
                camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

            # abort acquisition
            else:
                return constants.SUCCESS

            # main loop
            while self.acquiring.value == 1:

                image = camera.GetNextImage()

                #
                if not image.IsIncomplete():

                    # convert the image
                    frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)

                # release the image
                image.Release()

            result = constants.SUCCESS

        except PySpin.SpinnakerException:
            result = False

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
            camera.TriggerMode.SetValue(PySpin.TriggerMode_On)
            camera.LineSelector.SetValue(PySpin.LineSelector_Line1)
            camera.LineSource.SetValue(PySpin.LineSource_FrameTriggerWait)
            camera.LineInverter.SetValue(True)

            result = constants.SUCCESS

        except SpinnakerException:
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
            self._.iq.put(constants.INITIALIZE)
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

        # set the triggered flag to False
        self._triggered = False

        return

    def trigger(self):
        """
        trigger the camera
        """

        # start acquisition if necessary
        if not self.primed:
            logging.warning('Video acquisition is not started. Call the prime method.')
            return

        # set the triggered flag to True
        self._triggered = True

        # send the trigger state to the child process
        self._iq.put(self.triggered)

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

        # release the trigger if the camera is still waiting for it
        if not self.triggered:
            self._iq.put(self.triggered)

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

    # camera trigger state
    @property
    def triggered(self):
        return self._triggered
