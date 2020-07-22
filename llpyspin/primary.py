# imports
import logging
import numpy as np

# relative imports
import .constants as c
import .processes as p

# from .children import PrimaryCameraChildProcess

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

class PrimaryCamera():
    """
    """

    def __init__(self, serialno=None):
        """
        """

        # serial number
        self.serialno = c.PRIMARY_SERIALNO if serialno is None else serialno

        # set the default values
        self._framerate = c.CAP_PROP_FPS_DEFAULT
        self._binsize   = c.CAP_PROP_BINSIZE_DEFAULT,
        self._exposure  = c.CAP_PROP_EXPOSURE_DEFAULT
        self._mode      = c.CAP_PROP_BUFFER_HANDLING_MODE_RECORDING

        # prime the camera
        self.prime()

        return

    def _createChild(self):
        """
        create and start the child process
        """

        self._child = p.PrimaryCameraProcess(self.serialno)
        self._child.start()

        return

    def isAcquiring(self):
        """
        returns the state of acquisition
        """

        return True if self._child.acquiring.value == 1 else False

    def prime(self):
        """
        prime the camera for video acquisition
        """

        # check that the camera isn't acquiring
        try:
            assert self.isAcquiring() is False
        except AssertionError:
            logging.info('Video acquisition is already started.')
            return

        # (re-)start the child process if needed
        if not hasattr('_child') or not self._child.is_alive():
            self._createChild()

        # initialize the camera
        self._child.iq.put('initialize')
        result = self._child.oq.get()
        if not result:
            logging.error('Camera initialization failed.')
            return

        # set the acquisition properties
        for (property,value) in vars(self).items():
            if property.strip('_') in c.VALID_CAP_PROPS:
                self._set(property,value)

        # configure the camera
        self._child.iq.put('configure')
        result = self._child.oq.get()
        if not result:
            logging.error('Camera configuration failed.')
            return

        self._child.iq.put('acquire')

        return

    def trigger(self):
        """
        trigger the master camera
        """

        # start acquisition if necessary
        if self._child.acquiring.value == 0:
            logging.warning('Video acquisition is not started. Call the prime method.')
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
            assert self.isAcquiring() is True
        except AssertionError:
            logging.info('Video acquisition is already stopped.')
            return

        # break out of the acquisition loop
        self._child.acquiring.value = 0

        # retreive the result (sent after exiting the acquisition loop)
        result = self._child.oq.get()

        if not result:
            logging.warning('Video acquisition failed.')

        # stop acquisition
        self._child.iq.put('deacquire')
        result = self._child.oq.get()

        # check result
        if not result:
            logging.warning('Failed to stop video acquisition.')

        return

    def release(self):
        """
        """

        # stop acquisition if acquiring
        if self.isAcquiring() is True:
            logging.info('Stopping video acquisition.')
            self.stop()

        # deconfigure camera
        self._child.iq.put('deconfigure')
        result = self._child.oq.get()
        if not result:
            logging.warning('Camera deconfiguration failed.')

        # de-init the camera
        self._child.iq.put('deinitialize')
        result = self._child.oq.get()
        if not result:
            logging.warning('Camera deinitialization failed.')

        # stop and join the child process
        self._child.started.value = 0
        self._child.join()

        return

    def _set(self, property, value):
        """
        set the value of a valid acquisition property

        returns
        -------
        result : bool
            True if successul in setting new value of property else False
        """

        result = False

        # assert that acquisition is not ongoing
        try:
            assert self.isAcquiring() is False
        except:
            logging.warning(f'Failed to set {property} to {value} because video acquisition is ongoing.')
            return result

        # check that the requested property is valid
        try:
            assert property in [c.CAP_PROP_FPS, c.CAP_PROP_BINSIZE, c.CAP_PROP_EXPOSURE]

        except AssertionError:
            logging.warning(f'Failed to set {property} to {value} because {property} is not a valid property.')
            return result

        # stop the acquisition if started

        # communicate with the child process
        self._child.iq.put('set')
        self._child.iq.put(property)
        self._child.iq.put(value)

        result = self._child.oq.get()

        if not result:
            logging.warning(f'Failed to set {property} to {value}.')

        return result

    # framerate
    @property
    def framerate(self):
        return self._framerate
    @framerate.setter
    def framerate(self, value):
        result = self._set(c.CAP_PROP_FPS,value)
        if result:
            self._framerate = value

    # exposure
    @property
    def exposure(self):
        return self._exposure
    @exposure.setter
    def exposure(self, value):
        result = self._set(c.CAP_PROP_EXPOSURE,value)
        if result:
            self._exposure = value

    # binsize
    @property
    def binsize(self):
        return self._binsize
    @binsize.setter
    def binsize(self, value):
        result = self._set(c.CAP_PROP_BINSIZE,value)
        if result:
            self._binsize = value
