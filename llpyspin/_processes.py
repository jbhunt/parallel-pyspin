import dill
import types
import queue
import logging
import numpy as np
import multiprocessing as mp

# shared flags
_ACQUIRING = mp.Value('i', 0)

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# try to import the PySpin package
try:
    import PySpin
except ModuleNotFoundError:
    logging.error('PySpin import failed.')

class SubprocessError(Exception):
    """error raised for failed attempt to create child process"""
    def __init__(self, message):
        super().__init__(message)
        self.message = message
        return

class PropertyError(Exception):
    """error raised for failed attempts to set the value of an acquisition property"""

    def __init__(self, property, value):
        super().__init__()
        self.message = f'{value} is not a valid value for {property}'
        return

class CameraBaseV2(mp.Process):
    """
    """

    def __init__(self, device=0, **kwargs):
        """
        """

        self._device = device

        # queues
        if 'iq' in kwargs.keys():
            self._iq = kwargs['iq']
        else:
            self._iq = mp.Queue()
        if 'oq' in kwargs.keys():
            self._oq = kwargs['oq']
        else:
            self._oq = mp.Queue()
        if 'started' in kwargs.keys():
            self._started = kwargs['started']
        else:
            self._started = mp.Value('i', 1)

        #
        self._framerate = 1
        self._exposure  = 3000
        self._binsize   = 1

        #
        super().__init__()
        self.start()
        self.initialize()

        return

    def run(self):
        """
        """

        try:

            # create instances of the system and cameras list
            system  = PySpin.System.GetInstance()
            cameras = system.GetCameras()

            #
            assert len(cameras) != 0

            # instantiate the camera
            if type(self._device) == str:
                camera = cameras.GetBySerial(self._device)

            if type(self._device) == int:
                camera = cameras.GetByIndex(self._device)

        except:

            # clean-up
            try:
                del camera
            except NameError:
                pass
            cameras.Clear()
            del cameras
            system.ReleaseInstance()

            logging.log(logging.ERROR, f'failed to acquire camera[{self._device}]')

            return

        # main loop
        while self.started:

            try:

                # retrieve an item from the queue
                item = self._iq.get(block=False)

                # function with args
                if type(item) == list:
                    dilled, args = item
                    f = dill.loads(dilled)
                    result = f(camera, *args)

                # function without args
                elif type(item) == bytes:
                    f = dill.loads(item)
                    result = f(camera)

                # return the result
                self._oq.put(result)

            except queue.Empty:
                continue

        # clean up
        try:
            del camera
        except NameError:
            pass
        cameras.Clear()
        del cameras
        system.ReleaseInstance()

        return

    def initialize(self):
        """
        """

        def f(camera):
            try:

                #
                camera.Init()

                #
                camera.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
                camera.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
                camera.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_NewestOnly)

                # set the exposure
                camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                camera.AcquisitionFrameRateEnable.SetValue(False)
                camera.ExposureTime.SetValue(3000)

                # set the framerate
                camera.AcquisitionFrameRateEnable.SetValue(True)
                camera.AcquisitionFrameRate.SetValue(1)

                # binsize

                return True

            except PySpin.SpinnakerException:
                return False

        # send the function through the queue
        self._iq.put(dill.dumps(f))

        # retrieve the result of the function call
        result = self._oq.get()
        if result:
            logging.log(logging.INFO, f'camera[{self._device}] initialized')
        else:
            logging.log(loggin.ERROR, f'failed to initialize camera[{self._device}]')

        return

    def release(self):
        """
        """

        def f(camera):
            try:
                if camera.IsStreaming():
                    camera.EndAcquisition()
                camera.DeInit()
            except PySpin.SpinnakerException:
                return False

        # send the function through the queue
        self._iq.put(dill.dumps(f))

        # retrieve the result of the function call
        result = self._oq.get()
        if result:
            logging.log(logging.INFO, f'camera[{self._device}] released')
        else:
            logging.log(logging.ERROR, f'failed to release camera[{self._device}]')

        return

    # started flag which maintains the main loop
    @property
    def started(self):
        return True if self._started.value == 1 else False

    @started.setter
    def started(self, flag):
        if flag not in [0, 1, True, False]:
            raise ValueError('started flag can only be set to 0, 1, True, or False')
        self._started.value = 1 if flag == True else 0

    # framerate
    @property
    def framerate(self):

        def f(camera):
            value = camera.AcquisitionFrameRate.GetValue()
            return value

        self._iq.put(dill.dumps(f))
        value = int(np.around(self._oq.get()))

        #
        if value != self._framerate:
            logging.log(logging.ERROR, f'actual camera framerate of {value:.1f} fps does not equal the target framerate of {self._framerate} fps')
            return

        return value

    @framerate.setter
    def framerate(self, value):

        def f(camera, value):
            camera.AcquisitionFrameRateEnable.SetValue(True)
            min = camera.AcquisitionFrameRate.GetMin()
            max = camera.AcquisitionFrameRate.GetMax()
            if not min <= value <= max:
                return False
            else:
                try:
                    camera.AcquisitionFrameRate.SetValue(value)
                    if camera.AcquisitionFrameRate.GetValue() != value:
                        return False
                    else:
                        return True
                except PySpin.SpinnakerException:
                    return False

        #
        args = [value]
        item = (dill.dumps(f), args)
        self._iq.put(item)

        #
        result = self._oq.get()
        if result:
            self._framerate = value
            logging.log(logging.INFO, f'camera[{self._device}] framerate set to {value}')
        else:
            logging.log(logging.ERROR, f'failed to set camera[{self._device}] framerate to {value}')

        return

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

        # global variables
        global _ACQUIRING

        # private attributes

        self._child           = None            # attribute which holds the reference to the child process

        self._started         = mp.Value('i',0) # this flag controls the main loop in the run method
        # self._acquiring       = mp.Value('i',0) # this flag controls the acquisition loop in the _start method
        self._acquiring       = _ACQUIRING

        self._lock            = mp.Lock()       # acquisition lock
        self._locked          = False           # acquisition lock state

        self._iq              = mp.Queue()      # input queue
        self._oq              = mp.Queue()      # output queue

        # acquisition property private values
        self._framerate = None
        self._exposure  = None
        self._binsize   = None
        self._roi       = None

        # alternative naming
        # self._fps             = None
        # self._bin             = None
        # self._exp             = None

        return

    # TODO : the more I think about this, the more I think the child process
    #        should be made into its own class

    def _run(self):
        """
        target function for the child process

        notes
        -----
        Do not make logging calls (e.g., 'logging.info(<some informative message>)')
        within this method. Writing to stdout is not a process-safe operation.
        """

        try:

            # create instances of the system and cameras list
            system  = PySpin.System.GetInstance()
            cameras = system.GetCameras()

            #
            assert len(cameras) != 0

            # instantiate the camera
            if type(self.device) == str:
                camera = cameras.GetBySerial(self.device)

            if type(self.device) == int:
                camera = cameras.GetByIndex(self.device)

            # send the result back
            self._oq.put(True)

        except:

            # clean-up
            try:
                del camera
            except NameError:
                pass
            cameras.Clear()
            del cameras
            system.ReleaseInstance()

            # send the result back
            self._oq.put(False)

            return

        # set the started flag to True
        self.started = True

        # main loop
        while self.started:

            # listen for method calls from the main process
            try:
                item = self._iq.get(block=False)
                # print(item)

            except queue.Empty:
                continue

            # call the appropriate method
            try:
                method = self.__getattribute__('_' + item)
                method(camera)
                self._oq.put(True)

            # except PySpin.SpinnakerException:
            except:
                self._oq.put(False)

            continue

        # clean up
        try:
            del camera
        except NameError:
            pass
        cameras.Clear()
        del cameras
        system.ReleaseInstance()

        return

    def _spawn(self):
        """
        spawn the child process
        """

        if self._child != None:
            logging.debug('active child process detected')
            return

        logging.debug('creating the child process')

        # create the child process
        self._child = mp.Process(target=self._run,args=())

        # make the child a daemon process
        self._child.daemon = True

        # start the child process
        self._child.start()

        # the child will send back the result of the fork
        result = self._oq.get()
        if result == False:
            raise SubprocessError('failed to spawn child process')

        return

    def _kill(self):
        """
        kill the child process
        """

        if self._child == None:
            logging.debug('no active child process detected')
            return

        logging.debug('destroying the child process')

        # break out of the main loop in the child process
        self.started = False

        # empty out the queues - if the are not empty it can cause the call to the join method to hang
        if self._iq.qsize() != 0 or self._oq.qsize() != 0:
            logging.debug('emptying input and output queues')
            while not self._iq.empty(): item = self._iq.get()
            while not self._oq.empty(): item = self._oq.get()

        # join the child process
        self._child.join(timeout=15)
        if self._child.is_alive():
            logging.error('child process is deadlocked')
            self._child.terminate()
            self._child.join()

        # delete the reference to the child process
        self._child = None

        return

    # NOTE : this method is not yet implemented
    # TODO : implement this method

    def _send(self, item, caller='parent', *items):
        """
        put one or more items in the input queue

        keywords
        --------
        caller : str
            identity of the process (i.e., parent or child)

        notes
        -----
        The caller kwarg specifies which queue to put the item(s) in.
        """

        if caller == 'parent':
            q = self._iq
        elif caller == 'child':
            q = self._oq
        else:
            raise ValueError('invalid caller-ID')

        q.put(item)

        # option to send follow up data
        if len(items) != 0:
            q.put(items)

        return

    # retreive the result of a call from the output queue
    @property
    def _result(self):

        # try:
        #     result = self._oq.get(block=True, timeout=5)

        # except mp.TimeoutError:
        #     raise SubprocessError('failed to retreive result from output queue')

        # except queue.Empty:
        #     raise SubprocessError('failed to retreive result from output queue')

        result = self._oq.get()

        return result

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

    # acquisition lock state
    @property
    def locked(self):
        return self._locked

    @locked.setter
    def locked(self, value):

        # engage the lock
        if value == True:
            if self._locked:
                logging.debug('acquisition lock is already engaged')
                return
            result = self._lock.acquire(block=False)
            if result:
                logging.debug('acquisition lock engaged')
                self._locked = True
            else:
                logging.debug('failed to engage acquisition lock')

        # disengage the lock
        elif value == False:
            if not self._locked:
                logging.debug('acquisition lock is not engaged')
                return
            try:
                self._lock.release()
                logging.debug('acquisition lock disengaged')
                self._locked = False
            except ValueError:
                logging.debug('failed to disengage acquisition lock')

        else:
            raise ValueError('invalid acquisition lock state')
