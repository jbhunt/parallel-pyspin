import queue
import ctypes
import logging
import numpy as np
import multiprocessing as mp

# relative imports
from ._processes  import CameraBase
from ._spinnaker  import SpinnakerMixin
from ._properties import PropertiesMixin, AcquisitionProperty

#
from . import recording

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

        super().__init__(device)

        # private attributes
        self._primed   = False
        self._filename = mp.Value(ctypes.c_char_p, None)
        self._nickname = '<nickname>'

        logging.info('creating secondary camera')

        # create the child process
        self._spawn()

        # attempt to initialize the camera
        self._iq.put('initialize')
        if self._result == False:
            logging.error('camera initialization failed')
            return

        self.framerate = 60
        self.exposure  = 1500
        self.binsize   = None

        return

    ### private methods ###

    def _start(self, camera):
        """
        """

        args = self._iq.get()
        writer = recording.VideoWriter(*args)

        # configure the hardware trigger
        camera.TriggerSource.SetValue(PySpin.TriggerSource_Line3)
        camera.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
        camera.TriggerActivation.SetValue(PySpin.TriggerActivation_AnyEdge)
        camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

        # begin acquisition
        camera.BeginAcquisition()

        txtfile = open('/home/polegpolskylab/Desktop/cam2.txt', 'w')

        # main loop
        while self.acquiring == True:

            # There's a 1 ms timeout for the call to GetNextImage to prevent
            # the secondary camera from blocking when video acquisition is
            # aborted before the primary camera is triggered (see below).

            try:
                image = camera.GetNextImage(1) # timeout
            except PySpin.SpinnakerException:
                continue

            #
            if not image.IsIncomplete():

                # convert the image
                frame = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
                txtfile.write(str(frame.GetTimeStamp()) + '\n')

                #
                writer.write(frame)

            # release the image
            image.Release()

        #
        while True:
            try:
                image = camera.GetNextImage(1000) # timeout
            except PySpin.SpinnakerException:
                break

        writer.close()

        return

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

    def prime(self, filename):
        """
        prime the camera for video recording
        """

        # check that the camera isn't acquiring
        # if self.primed == True:
        #     logging.info('camera is already primed')
        #     return

        if not filename.endswith('.avi'):
            raise ValueError('filename string must end with ".avi" extension')

        # overwrite the current filename
        self.filename = filename

        # set the acquiring flag to 1
        # self.acquiring = True

        # send the acquisition command
        self._iq.put('start')

        #
        args = [filename, None, self.framerate, (self.roi[2:])]
        self._iq.put(args)

        # acquire acquisition lock
        self.locked = True

        return

    def stop(self):
        """
        stop video acquisition
        """

        # check that the camera is acquiring
        # if self.acquiring == False:
        #     logging.info('video acquisition is already stopped')
        #     return

        # break out of the acquisition loop
        # self.acquiring = False

        # retreive the result (sent after exiting the acquisition loop)
        if self._result == False:
            logging.debug('video acquisition failed')

        # stop acquisition
        self._iq.put('stop')
        if self._result == False:
            logging.debug('video de-acquisition failed')

        # release acquisition lock
        self.locked = False

        return

    def release(self):
        """
        release the camera
        """

        if self.started == False:
            logging.info('camera already released')
            return

        # stop acquisition if acquiring
        if self.primed == True:
            logging.info('stopping video acquisition')
            self.stop()

        #
        self._iq.put('release')
        if self._result == False:
            logging.debug('camera de-initialization failed')

        # stop and join the child process
        self._kill()

        return

    # nickname
    @property
    def nickname(self):
        return self._nickname
    @nickname.setter
    def nickname(self, value):
        self._nickname = value

    # filename
    @property
    def filename(self):
        return self._filename.value.decode()

    @filename.setter
    def filename(self, value):
        if type(value) is not str:
            raise ValueError('filename must be a string')
        self._filename.value = value.encode()

    # camera ready state
    @property
    def primed(self):
        self._primed = True if self._child is not None and self.acquiring == 1 else False
        return self._primed

    # overwrite the framerate and exposure properties

    @AcquisitionProperty
    def framerate(self):
        return self._framerate

    @framerate.setter
    def framerate(self, value):
        logging.debug('framerate is set by the primary camera')
        self._framerate = value

    @AcquisitionProperty
    def exposure(self):
        return self._exposure

    @exposure.setter
    def exposure(self, value):
        logging.debug('exposure is set by the primary camera')
        self._exposure = value
