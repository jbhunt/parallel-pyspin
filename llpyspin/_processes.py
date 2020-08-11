import types
import queue
import logging
import numpy as np
import multiprocessing as mp

# import all constants
from ._constants import *

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

class CameraBase():
    """
    this is the base class for any subclass of camera which handles the creation,
    operation, and destruction of the child process
    """

    def __init__(self, device):
        """
        keywords
        --------
        device : int or str
            the camera's index or serial number
        """

        self.device = device
        self.child  = None

        # private attributes
        self._started         = mp.Value('i',0) # this flag controls the main loop in the run method
        self._acquiring       = mp.Value('i',0) # this flag controls the acquisition loop in the _start method
        self._iq              = mp.Queue()      # input queue
        self._oq              = mp.Queue()      # output queue

        # acquisition properties
        self._framerate       = FRAMERATE_DEFAULT_VALUE
        self._exposure        = EXPOSURE_DEFAULT_VALUE
        self._binsize         = BINSIZE_DEFAULT_VALUE
        self._roi             = None

        # maps the command signatures to the appropriate class method
        self._map = {
            INITIALIZE : self._initialize,
            SET        : self._set,
            GET        : self._get,
            START      : self._start,
            STOP       : self._stop,
            RELEASE    : self._release
        }

        return

    # started flag
    @property
    def started(self): return True if self._started.value == 1 else False

    @started.setter
    def started(self, value):
        self._started.value = 1 if value == True else False

    # acquiring flag
    @property
    def acquiring(self): return True if self._acquiring.value == 1 else False

    @acquiring.setter
    def acquiring(self, value):
        self._acquiring.value = 1 if value == True else False

    def _run(self):
        """
        target function for the child process

        notes
        -----
        Do not make logging calls (e.g., 'logging.info(<some informative message>)')
        within this method. Writing to stdout is not a process-safe operation.
        """

        # create instances of the system and cameras
        system  = PySpin.System.GetInstance()
        cameras = system.GetCameras()

        # assert at least one camera
        if len(cameras) == 0:
            raise Exception('no cameras detected')

        # instantiate the camera
        try:

            if type(self.device) == str:
                camera = cameras.GetBySerial(self.device)

            if type(self.device) == int:
                camera = cameras.GetByIndex(self.device)

            if type(self.device) not in [str,int]:
                cameras.Clear()
                system.ReleaseInstance()
                raise TypeError(f"The 'device' argument must be a string or integer but is {type(self.device)}.")

        except PySpin.SpinnakerException:
            cameras.Clear()
            system.ReleaseInstance()
            raise Exception('unable to create an instance of the camera')

        # set the started flag to True
        self.started = True

        # main loop
        while self.started:

            # listen for method calls from the main process
            try:
                item = self._iq.get(block=False)

            except queue.Empty:
                continue

            # call the appropriate class method
            result = self._map[item](camera)

            # return the result of the call to the main process
            self._oq.put(result)

            continue

        # clean up
        try:
            del camera
        except NameError:
            pass
        cameras.Clear()
        system.ReleaseInstance()

        return

    def _create(self):
        """
        create the child process
        """

        try:
            assert self.child is None
        except AssertionError:
            logging.warning("A child process already exists. To create a new instance call the '_destroy' method first.")
            return

        logging.debug('Creating the child process.')

        # create the child process
        self.child = mp.Process(target=self._run,args=())

        # start he child process
        self.child.start()

        return

    def _destroy(self):
        """
        destroy the child process
        """

        try:
            assert self.child is not None
        except AssertionError:
            logging.warning('no existing child process')
            return

        logging.debug('destroying the child process')

        # break out of the main loop in the child process
        self.started = False

        # empty out the queues - if the are not empty it can cause the call to the join method to hang
        if self._iq.qsize() != 0 or self._oq.qsize() != 0:
            logging.info('emptying out input and output queues')
            while not self._iq.empty():
                item = self._iq.get()
                logging.info(f"{item} removed from the input queue")
            while not self._oq.empty():
                item = self._oq.get()
                logging.info(f"{item} removed from the output queue")

        # join the child process
        try:
            self.child.join(1) # 1" timeout
        except mp.TimeoutError:
            logging.warning('the child process is deadlocked')
            self.child.terminate()
            self.child.join()

        # delete the reference to the child process
        self.child = None

        return
